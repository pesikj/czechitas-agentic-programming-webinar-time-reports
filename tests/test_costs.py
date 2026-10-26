from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from tests.test_reports import entry

pytestmark = pytest.mark.django_db


def test_project_total_uses_snapshot_and_drafts_are_separate(world):
    from reports.costs import monthly_costs
    from reports.services import reopen_report, submit_report

    entry(world, 90)
    entry(world, 60, 1)
    rows = monthly_costs(actor=world["manager"], month=date(2026, 10, 1))
    assert {r["code"]: r["estimate"] for r in rows} == {
        "WEB": Decimal("1200.00"),
        "DATA": Decimal("1000.00"),
    }
    assert all(r["cost"] == 0 for r in rows)
    submit_report(actor=world["person"], report_id=world["report"].pk)
    terms = world["assignments"][0].terms.get()
    terms.hourly_rate = Decimal("999")
    terms.save()
    rows = monthly_costs(actor=world["manager"], month=date(2026, 10, 1))
    assert sum(r["cost"] for r in rows) == Decimal("2200.00")
    reopen_report(actor=world["manager"], report_id=world["report"].pk, reason="Oprava")
    assert sum(
        r["estimate"] for r in monthly_costs(actor=world["manager"], month=date(2026, 10, 1))
    ) == Decimal("2200.00")


def test_round_only_project_total_half_up(world):
    from reports.costs import monthly_costs
    from reports.services import submit_report

    terms = world["assignments"][0].terms.get()
    terms.hourly_rate = Decimal("1.50")
    terms.save()
    entry(world, 1)
    entry(world, 1)
    submit_report(actor=world["person"], report_id=world["report"].pk)
    assert monthly_costs(actor=world["manager"], month=date(2026, 10, 1))[0]["cost"] == Decimal(
        "0.05"
    )


def test_costs_forbidden_and_missing_rate_marks_estimate_incomplete(world, client):
    from reports.costs import monthly_costs

    entry(world, 60)
    world["assignments"][0].terms.all().delete()
    with pytest.raises(PermissionDenied):
        monthly_costs(actor=world["person"], month=date(2026, 10, 1))
    rows = monthly_costs(actor=world["manager"], month=date(2026, 10, 1))
    assert rows[0]["incomplete"] is True
    client.force_login(world["person"])
    assert client.get("/costs/").status_code == 403
