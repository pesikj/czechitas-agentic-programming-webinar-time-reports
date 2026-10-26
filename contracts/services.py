from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from common.locking import lock_person
from common.models import audit
from common.permissions import require_manager

from .models import ContractTerms


def terms_for(assignment, month):
    try:
        return (
            ContractTerms.objects.filter(assignment=assignment, start_month__lte=month)
            .filter(Q(end_month__isnull=True) | Q(end_month__gte=month))
            .get()
        )
    except (ContractTerms.DoesNotExist, ContractTerms.MultipleObjectsReturned):
        raise ValidationError(
            f"Chybí jednoznačné smluvní podmínky pro {assignment.project} v {month:%m/%Y}."
        )


def _validate_history(user_id):
    from reports.models import MonthlyReport
    from reports.validation import validate_report

    for report in MonthlyReport.objects.filter(user_id=user_id, status="submitted"):
        issues = validate_report(report, historical=True)
        if issues:
            raise ValidationError(
                ["Změna by zneplatnila odeslaný výkaz."] + [i.message for i in issues]
            )


@transaction.atomic
def save_terms(*, actor, terms):
    require_manager(actor)
    lock_person(terms.assignment.user_id)
    if terms.pk:
        original = ContractTerms.objects.get(pk=terms.pk)
        if original.assignment_id != terms.assignment_id:
            raise ValidationError("Přiřazení existujících podmínek nelze změnit.")
    terms.full_clean()
    terms.save()
    _validate_history(terms.assignment.user_id)
    audit(actor, "terms.save", terms)
    return terms


@transaction.atomic
def save_assignment(*, actor, assignment):
    require_manager(actor)
    lock_person(assignment.user_id)
    if assignment.pk:
        from .models import Assignment

        original = Assignment.objects.get(pk=assignment.pk)
        if (original.user_id, original.project_id) != (assignment.user_id, assignment.project_id):
            raise ValidationError("Osobu a projekt existujícího přiřazení nelze změnit.")
    assignment.full_clean()
    assignment.save()
    _validate_history(assignment.user_id)
    audit(actor, "assignment.save", assignment)
    return assignment
