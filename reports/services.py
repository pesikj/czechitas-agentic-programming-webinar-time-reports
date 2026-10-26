from datetime import date as date_type
from decimal import Decimal, DecimalException

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from common.locking import lock_person
from common.models import audit
from common.permissions import require_manager, require_owner_or_manager
from contracts.models import Assignment
from contracts.services import terms_for

from .models import MonthlyReport, TimeEntry
from .validation import validate_report


def hours_to_minutes(value):
    try:
        number = Decimal(str(value).strip().replace(",", "."))
        if not number.is_finite() or number <= 0 or number > 1000000:
            raise ValueError
        minutes = number * 60
        if (
            not number.is_finite()
            or minutes <= 0
            or minutes != minutes.to_integral_value()
            or minutes > 1000000
        ):
            raise ValueError
        return int(minutes)
    except (DecimalException, ValueError, TypeError, OverflowError):
        raise ValidationError("Zadejte kladné hodiny odpovídající celým minutám (např. 1,5).")


def _locked_report(actor, report_id):
    report = MonthlyReport.objects.get(pk=report_id)
    require_owner_or_manager(actor, report.user_id)
    lock_person(report.user_id)
    return MonthlyReport.objects.select_for_update().get(pk=report_id)


def _editable(report):
    if report.status != "draft":
        raise ValidationError("Odeslaný výkaz je zamčený. Správce ho musí nejprve vrátit k opravě.")


@transaction.atomic
def get_or_create_report(*, actor, user_id, month):
    require_owner_or_manager(actor, user_id)
    lock_person(user_id)
    if not isinstance(month, date_type) or month.day != 1:
        raise ValidationError("Vyberte první den měsíce.")
    return MonthlyReport.objects.get_or_create(user_id=user_id, month=month)[0]


@transaction.atomic
def save_entry(*, actor, report_id, assignment_id, date, minutes, description, entry_id=None):
    report = _locked_report(actor, report_id)
    _editable(report)
    assignment = Assignment.objects.select_related("project").get(pk=assignment_id)
    if assignment.user_id != report.user_id:
        raise PermissionDenied
    if not assignment.is_active or not assignment.project.is_active:
        raise ValidationError("Projekt nebo přiřazení není aktivní.")
    if (
        date.replace(day=1) != report.month
        or date < assignment.start
        or (assignment.end and date > assignment.end)
    ):
        raise ValidationError("Datum není v měsíci výkazu nebo období přiřazení.")
    if (
        isinstance(minutes, bool)
        or not isinstance(minutes, int)
        or minutes <= 0
        or minutes > 1000000
    ):
        raise ValidationError("Čas musí být kladný počet celých minut.")
    if len(description) > 1000:
        raise ValidationError("Popis může mít nejvýše 1000 znaků.")
    e = TimeEntry.objects.get(pk=entry_id, report=report) if entry_id else TimeEntry(report=report)
    if e.pk and e.assignment_id != assignment.pk:
        e.rate_snapshot = None
    e.assignment = assignment
    e.date = date
    e.minutes = minutes
    e.description = description
    e.full_clean()
    e.save()
    return e


@transaction.atomic
def delete_entry(*, actor, entry_id):
    entry = TimeEntry.objects.get(pk=entry_id)
    report = _locked_report(actor, entry.report_id)
    _editable(report)
    entry.delete()


@transaction.atomic
def submit_report(*, actor, report_id, historical=False):
    report = _locked_report(actor, report_id)
    _editable(report)
    if historical:
        require_manager(actor)
    issues = validate_report(report, historical=historical)
    if issues:
        raise ValidationError([i.message for i in issues])
    for e in report.entries.select_related("assignment__project"):
        if e.rate_snapshot is None:
            e.rate_snapshot = terms_for(e.assignment, report.month).hourly_rate
            e.save(update_fields=["rate_snapshot"])
    report.status = "submitted"
    report.submitted_at = timezone.now()
    report.save(update_fields=["status", "submitted_at"])
    audit(actor, "report.submit", report, historical=historical)
    return report


@transaction.atomic
def reopen_report(*, actor, report_id, reason):
    require_manager(actor)
    report = _locked_report(actor, report_id)
    if not reason.strip():
        raise ValidationError("Uveďte důvod vrácení výkazu.")
    if report.status != "submitted":
        raise ValidationError("Výkaz už je rozpracovaný.")
    report.status = "draft"
    report.save(update_fields=["status"])
    audit(actor, "report.reopen", report, reason=reason[:1000])
    return report


@transaction.atomic
def reprice_report(*, actor, report_id, reason):
    require_manager(actor)
    report = _locked_report(actor, report_id)
    _editable(report)
    if not reason.strip():
        raise ValidationError("Uveďte důvod přepočtu sazeb.")
    for e in report.entries.select_related("assignment__project"):
        e.rate_snapshot = terms_for(e.assignment, report.month).hourly_rate
        e.save(update_fields=["rate_snapshot"])
    audit(actor, "report.reprice", report, reason=reason[:1000])
    return report
