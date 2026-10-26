import hashlib
from collections import defaultdict
from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from common.locking import lock_person
from common.models import audit
from common.permissions import require_manager
from contracts.models import Assignment
from reports.models import MonthlyReport, TimeEntry
from reports.services import hours_to_minutes, submit_report
from reports.validation import validate_report

from .models import ImportBatch
from .parsers import parse_upload


def _access(actor, batch, allow_completed=False):
    require_manager(actor)
    if batch.owner_id != actor.pk:
        raise PermissionDenied
    if batch.status == "completed" and allow_completed:
        return
    if batch.expires_at <= timezone.now():
        raise ValidationError("Platnost importu vypršela. Nahrajte soubor znovu.")
    if batch.status == "completed":
        raise ValidationError("Tento import už byl dokončen.")


@transaction.atomic
def upload_batch(*, actor, file, sheet=None):
    require_manager(actor)
    lock_person(actor.pk)
    if (
        ImportBatch.objects.filter(
            owner=actor, created_at__gte=timezone.now() - timedelta(hours=1)
        ).count()
        >= 20
    ):
        raise ValidationError("Za hodinu lze připravit nejvýše 20 importů. Zkuste to později.")
    table, data = parse_upload(file, sheet=sheet)
    fingerprint = hashlib.sha256(data + b"\0" + table["sheet"].encode("utf-8")).hexdigest()
    if ImportBatch.objects.filter(fingerprint=fingerprint, status="completed").exists():
        raise ValidationError("Tento soubor již byl importován.")
    return ImportBatch.objects.create(
        owner=actor,
        filename=file.name[:255],
        fingerprint=fingerprint,
        table=table,
        expires_at=timezone.now() + timedelta(hours=24),
    )


def _normalize(table, mapping):
    headers = table["headers"]
    errors = []
    rows = []
    duplicates = []
    seen = set()
    if any(mapping.get(key) not in headers for key in ["date", "user", "project", "hours"]):
        return [], ["Vyberte všechny povinné sloupce."], []
    mapped = [mapping[k] for k in ["date", "user", "project", "hours"]]
    if len(set(mapped)) != 4:
        return [], ["Každá povinná hodnota musí mít vlastní sloupec."], []
    for rowno, cells in enumerate(table["rows"], start=2):
        if not any(cells):
            continue
        record = dict(zip(headers, cells))
        try:
            day = None
            for fmt in ["%Y-%m-%d", "%d.%m.%Y", "%d. %m. %Y"]:
                try:
                    day = datetime.strptime(record.get(mapping["date"], ""), fmt).date()
                    break
                except ValueError:
                    continue
            if day is None:
                raise ValidationError("Neplatné datum. Použijte RRRR-MM-DD nebo DD.MM.RRRR.")
            identity = record.get(mapping["user"], "")
            users = User.objects.filter(Q(username__iexact=identity) | Q(email__iexact=identity))
            if users.count() != 1:
                raise ValidationError("Neznámý nebo nejednoznačný externista: " + identity)
            user = users.get()
            try:
                a = Assignment.objects.select_related("project", "user").get(
                    user=user, project__code=record.get(mapping["project"], "")
                )
            except Assignment.DoesNotExist:
                raise ValidationError("Neznámý projekt nebo chybějící přiřazení.")
            minutes = hours_to_minutes(record.get(mapping["hours"], ""))
            description = record.get(mapping.get("description", ""), "")
            if len(description) > 1000:
                raise ValidationError("Popis může mít nejvýše 1000 znaků.")
            normalized = {
                "row": rowno,
                "date": day.isoformat(),
                "user_id": user.pk,
                "user_label": str(user),
                "assignment_id": a.pk,
                "project_code": a.project.code,
                "minutes": minutes,
                "description": description,
            }
            key = (day, user.pk, a.pk, minutes, description)
            if key in seen:
                duplicates.append(rowno)
            seen.add(key)
            rows.append(normalized)
        except ValidationError as exc:
            errors.extend(f"Řádek {rowno}: {message}" for message in exc.messages)
    if not rows and not errors:
        errors.append("Soubor neobsahuje žádné pracovní záznamy.")
    errors.extend(_validate_rows(rows))
    return rows, errors, duplicates


def _validate_rows(rows):
    groups = defaultdict(list)
    errors = []
    for row in rows:
        groups[(row["user_id"], row["date"][:7])].append(row)
    for (uid, month), records in groups.items():
        month = datetime.strptime(month + "-01", "%Y-%m-%d").date()
        if MonthlyReport.objects.filter(user_id=uid, month=month).exists():
            errors.append(
                f"{records[0]['user_label']}, {month:%m/%Y}: výkaz pro tento měsíc již existuje."
            )
            continue
        report = MonthlyReport(user_id=uid, month=month)
        entries = []
        for row in records:
            try:
                a = Assignment.objects.select_related("project", "user").get(
                    pk=row["assignment_id"], user_id=uid
                )
            except Assignment.DoesNotExist:
                errors.append(f"Řádek {row['row']}: přiřazení již neexistuje.")
                continue
            entries.append(
                TimeEntry(
                    report=report,
                    assignment=a,
                    date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                    minutes=row["minutes"],
                    description=row["description"],
                )
            )
        errors.extend(
            f"{records[0]['user_label']}, {month:%m/%Y}: {i.message}"
            for i in validate_report(report, historical=True, entries=entries)
        )
    return errors


@transaction.atomic
def map_batch(*, actor, batch_id, mapping):
    batch = ImportBatch.objects.select_for_update().get(pk=batch_id)
    _access(actor, batch)
    batch.rows, batch.errors, batch.duplicates = _normalize(batch.table, mapping)
    batch.mapping = mapping
    batch.status = "ready"
    batch.save()
    return batch


def prepare_batch(*, actor, file, mapping, sheet=None):
    batch = upload_batch(actor=actor, file=file, sheet=sheet)
    return map_batch(actor=actor, batch_id=batch.pk, mapping=mapping)


@transaction.atomic
def confirm_batch(*, actor, batch_id, accept_duplicates=False):
    batch = ImportBatch.objects.select_for_update().get(pk=batch_id)
    _access(actor, batch, allow_completed=True)
    if batch.status == "completed":
        return batch.result
    if batch.status != "ready":
        raise ValidationError("Nejprve dokončete mapování sloupců.")
    if batch.errors:
        raise ValidationError(batch.errors)
    if batch.duplicates and not accept_duplicates:
        raise ValidationError("Soubor obsahuje shodné řádky. Potvrďte výslovně, že jsou správné.")
    for uid in sorted({r["user_id"] for r in batch.rows}):
        lock_person(uid)
    # Serialize completion for a fingerprint even for batches owned by different managers.
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [int(batch.fingerprint[:15], 16)])
    if ImportBatch.objects.filter(fingerprint=batch.fingerprint, status="completed").exists():
        raise ValidationError("Tento soubor již byl importován.")
    # Re-resolve identity/assignment and current contracts from the immutable stored table.
    rows, errors, duplicates = _normalize(batch.table, batch.mapping)
    if rows != batch.rows:
        raise ValidationError(
            "Přiřazení nebo identity se od náhledu změnily. Připravte nový náhled."
        )
    if errors:
        raise ValidationError(errors)
    groups = defaultdict(list)
    for row in rows:
        groups[(row["user_id"], row["date"][:7])].append(row)
    for (uid, month), records in groups.items():
        report = MonthlyReport.objects.create(user_id=uid, month=month + "-01")
        report.refresh_from_db()
        for row in records:
            e = TimeEntry(
                report=report,
                assignment_id=row["assignment_id"],
                date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                minutes=row["minutes"],
                description=row["description"],
            )
            e.full_clean()
            e.save()
        submit_report(actor=actor, report_id=report.pk, historical=True)
    batch.status = "completed"
    batch.result = {"reports": len(groups), "entries": len(rows)}
    batch.rows = []
    batch.table = {}
    batch.save()
    audit(actor, "import.complete", batch, **batch.result)
    return batch.result
