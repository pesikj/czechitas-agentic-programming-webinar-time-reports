from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

pytestmark = pytest.mark.django_db


def test_overlapping_terms_rejected():
    from accounts.models import User
    from contracts.models import Assignment, ContractTerms, Project
    from contracts.services import save_terms

    admin = User.objects.create_user("manager", email="manager@example.com", is_staff=True)
    user = User.objects.create_user("person", email="person@example.com")
    project = Project.objects.create(code="P1", name="Projekt")
    assignment = Assignment.objects.create(user=user, project=project, start=date(2026, 1, 1))
    save_terms(
        actor=admin,
        terms=ContractTerms(
            assignment=assignment,
            start_month=date(2026, 1, 1),
            end_month=date(2026, 12, 1),
            hourly_rate=Decimal("800"),
            monthly_limit_minutes=600,
        ),
    )
    with pytest.raises(ValidationError):
        save_terms(
            actor=admin,
            terms=ContractTerms(
                assignment=assignment,
                start_month=date(2026, 6, 1),
                hourly_rate=Decimal("900"),
                monthly_limit_minutes=600,
            ),
        )
    assert ContractTerms.objects.count() == 1


def test_contractor_cannot_manage_terms():
    from django.core.exceptions import PermissionDenied

    from accounts.models import User
    from contracts.models import ContractTerms
    from contracts.services import save_terms

    user = User.objects.create_user("person", email="person@example.com")
    with pytest.raises(PermissionDenied):
        save_terms(actor=user, terms=ContractTerms())
