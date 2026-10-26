from datetime import date

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

pytestmark = pytest.mark.django_db


def entry(w, minutes, assignment=0, day=1):
    from reports.services import save_entry

    return save_entry(
        actor=w["person"],
        report_id=w["report"].pk,
        assignment_id=w["assignments"][assignment].pk,
        date=date(2026, 10, day),
        minutes=minutes,
        description="Práce na projektu",
    )


def test_480_minutes_allowed(world):
    from reports.services import submit_report

    entry(world, 300)
    entry(world, 180, 1)
    result = submit_report(actor=world["person"], report_id=world["report"].pk)
    assert result.status == "submitted"
    assert all(e.rate_snapshot is not None for e in result.entries.all())


def test_481_minutes_across_projects_blocks_whole_submission(world):
    from reports.services import submit_report

    entry(world, 300)
    entry(world, 181, 1)
    with pytest.raises(ValidationError):
        submit_report(actor=world["person"], report_id=world["report"].pk)
    world["report"].refresh_from_db()
    assert world["report"].status == "draft"
    assert not world["report"].entries.exclude(rate_snapshot=None).exists()


@pytest.mark.parametrize("extra,allowed", [(0, True), (1, False)])
def test_monthly_limit_boundary(world, extra, allowed):
    from reports.services import submit_report

    entry(world, 480, day=1)
    entry(world, 480, day=2)
    entry(world, 240 + extra, day=3)
    if allowed:
        assert (
            submit_report(actor=world["person"], report_id=world["report"].pk).status == "submitted"
        )
    else:
        with pytest.raises(ValidationError):
            submit_report(actor=world["person"], report_id=world["report"].pk)


def test_wrong_month_or_assignment_rejected(world):
    from reports.services import save_entry

    with pytest.raises(ValidationError):
        save_entry(
            actor=world["person"],
            report_id=world["report"].pk,
            assignment_id=world["assignments"][0].pk,
            date=date(2026, 11, 1),
            minutes=60,
            description="",
        )
    with pytest.raises(PermissionDenied):
        save_entry(
            actor=world["other"],
            report_id=world["report"].pk,
            assignment_id=world["assignments"][0].pk,
            date=date(2026, 10, 1),
            minutes=60,
            description="",
        )


def test_submitted_entries_locked_and_reopen_requires_reason(world):
    from reports.services import delete_entry, reopen_report, submit_report

    e = entry(world, 60)
    submit_report(actor=world["person"], report_id=world["report"].pk)
    with pytest.raises(ValidationError):
        delete_entry(actor=world["person"], entry_id=e.pk)
    with pytest.raises(PermissionDenied):
        reopen_report(actor=world["person"], report_id=world["report"].pk, reason="Oprava")
    with pytest.raises(ValidationError):
        reopen_report(actor=world["manager"], report_id=world["report"].pk, reason="")
    assert (
        reopen_report(
            actor=world["manager"], report_id=world["report"].pk, reason="Oprava dne"
        ).status
        == "draft"
    )
    e.refresh_from_db()
    assert str(e.rate_snapshot) == "800.00"


def test_missing_terms_and_empty_report_rejected(world):
    from reports.services import submit_report

    with pytest.raises(ValidationError):
        submit_report(actor=world["person"], report_id=world["report"].pk)
    entry(world, 60)
    world["assignments"][0].terms.all().delete()
    with pytest.raises(ValidationError):
        submit_report(actor=world["person"], report_id=world["report"].pk)


def test_retroactive_limit_change_cannot_invalidate_submitted_report(world):
    from contracts.services import save_terms
    from reports.services import submit_report

    entry(world, 120)
    submit_report(actor=world["person"], report_id=world["report"].pk)
    terms = world["assignments"][0].terms.get()
    terms.monthly_limit_minutes = 60
    with pytest.raises(ValidationError):
        save_terms(actor=world["manager"], terms=terms)
    terms.refresh_from_db()
    assert terms.monthly_limit_minutes == 1200


def test_forged_report_id_cannot_read_or_write(world, client):
    client.force_login(world["other"])
    assert client.get(f"/reports/{world['report'].pk}/").status_code == 403
    assert client.post(f"/reports/{world['report'].pk}/submit/").status_code == 403


def test_reprice_requires_manager_reason_and_draft(world):
    from decimal import Decimal

    from reports.services import reopen_report, reprice_report, submit_report

    item = entry(world, 60)
    submit_report(actor=world["person"], report_id=world["report"].pk)
    with pytest.raises(ValidationError):
        reprice_report(actor=world["manager"], report_id=world["report"].pk, reason="Oprava sazby")
    reopen_report(actor=world["manager"], report_id=world["report"].pk, reason="Oprava")
    terms = world["assignments"][0].terms.get()
    terms.hourly_rate = Decimal("900")
    terms.save()
    with pytest.raises(PermissionDenied):
        reprice_report(actor=world["person"], report_id=world["report"].pk, reason="Oprava")
    with pytest.raises(ValidationError):
        reprice_report(actor=world["manager"], report_id=world["report"].pk, reason="")
    item.refresh_from_db()
    assert item.rate_snapshot == Decimal("800")
    reprice_report(
        actor=world["manager"], report_id=world["report"].pk, reason="Smlouva opravena na 900 Kč/h"
    )
    item.refresh_from_db()
    assert item.rate_snapshot == Decimal("900")


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity", "0,001", "1e100", "1e999999", ""])
def test_invalid_hours_rejected(value):
    from reports.services import hours_to_minutes

    with pytest.raises(ValidationError):
        hours_to_minutes(value)


def test_project_history_cannot_be_deleted(world):
    from django.db.models.deletion import ProtectedError

    entry(world, 60)
    with pytest.raises(ProtectedError):
        world["assignments"][0].project.delete()
