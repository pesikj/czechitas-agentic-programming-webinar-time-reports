from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections

pytestmark = pytest.mark.django_db(transaction=True)


def race(*functions):
    barrier = Barrier(len(functions))

    def run(fn):
        close_old_connections()
        barrier.wait(timeout=10)
        try:
            return fn()
        except ValidationError:
            return "rejected"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=len(functions)) as pool:
        futures = [pool.submit(run, f) for f in functions]
        return [f.result(timeout=20) for f in futures]


def test_edit_racing_submit_keeps_submitted_report_valid(world):
    from reports.services import save_entry, submit_report
    from reports.validation import validate_report
    from tests.test_reports import entry

    entry(world, 480)
    race(
        lambda: submit_report(actor=world["person"], report_id=world["report"].pk),
        lambda: save_entry(
            actor=world["person"],
            report_id=world["report"].pk,
            assignment_id=world["assignments"][1].pk,
            date=date(2026, 10, 1),
            minutes=1,
            description="",
        ),
    )
    world["report"].refresh_from_db()
    if world["report"].status == "submitted":
        assert not validate_report(world["report"])
    else:
        assert sum(e.minutes for e in world["report"].entries.all()) == 481


def test_concurrent_month_creation_unique(world):
    from reports.models import MonthlyReport
    from reports.services import get_or_create_report

    race(
        *[
            lambda: get_or_create_report(
                actor=world["person"], user_id=world["person"].pk, month=date(2026, 11, 1)
            )
            for _ in range(2)
        ]
    )
    assert MonthlyReport.objects.filter(user=world["person"], month=date(2026, 11, 1)).count() == 1


def test_terms_change_racing_submit_serialized(world):
    from contracts.services import save_terms
    from reports.services import submit_report
    from reports.validation import validate_report
    from tests.test_reports import entry

    entry(world, 120)
    terms = world["assignments"][0].terms.get()
    terms.monthly_limit_minutes = 60
    race(
        lambda: submit_report(actor=world["person"], report_id=world["report"].pk),
        lambda: save_terms(actor=world["manager"], terms=terms),
    )
    world["report"].refresh_from_db()
    if world["report"].status == "submitted":
        assert not validate_report(world["report"])
    else:
        assert world["assignments"][0].terms.get().monthly_limit_minutes == 60


def test_concurrent_import_and_manual_month_creation_atomic(world):
    from imports.services import confirm_batch, prepare_batch
    from reports.models import MonthlyReport
    from reports.services import get_or_create_report
    from tests.test_imports import MAPPING, csv_file

    batch = prepare_batch(actor=world["manager"], file=csv_file(), mapping=MAPPING)
    race(
        lambda: confirm_batch(actor=world["manager"], batch_id=batch.pk),
        lambda: get_or_create_report(
            actor=world["person"], user_id=world["person"].pk, month=date(2026, 9, 1)
        ),
    )
    assert MonthlyReport.objects.filter(user=world["person"], month=date(2026, 9, 1)).count() == 1
    report = MonthlyReport.objects.get(user=world["person"], month=date(2026, 9, 1))
    if report.status == "submitted":
        assert report.entries.count() == 1
    else:
        assert not report.entries.exists()


def test_concurrent_terms_creation_rejects_overlap(world):
    from decimal import Decimal

    from contracts.models import ContractTerms
    from contracts.services import save_terms

    world["assignments"][0].terms.all().delete()

    def create_terms():
        return save_terms(
            actor=world["manager"],
            terms=ContractTerms(
                assignment=world["assignments"][0],
                start_month=date(2026, 1, 1),
                hourly_rate=Decimal("800"),
                monthly_limit_minutes=1200,
            ),
        )

    race(create_terms, create_terms)
    assert ContractTerms.objects.filter(assignment=world["assignments"][0]).count() == 1


def test_concurrent_absence_creation_rejects_overlap(world):
    from datetime import timedelta

    from django.utils import timezone

    from calendar_app.models import Absence
    from calendar_app.services import save_absence

    day = timezone.localdate() + timedelta(days=14)

    def create_absence():
        return save_absence(actor=world["person"], user_id=world["person"].pk, start=day, end=day)

    race(create_absence, create_absence)
    assert Absence.objects.filter(user=world["person"]).count() == 1
