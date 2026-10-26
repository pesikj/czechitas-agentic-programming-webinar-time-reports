from datetime import date, datetime
from datetime import timezone as dt_timezone
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied, ValidationError

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("start,allowed", [(date(2026, 11, 8), True), (date(2026, 11, 7), False)])
def test_notice_boundary(world, start, allowed):
    from calendar_app.services import save_absence

    with patch(
        "django.utils.timezone.now", return_value=datetime(2026, 10, 25, 12, tzinfo=dt_timezone.utc)
    ):
        kwargs = dict(actor=world["person"], user_id=world["person"].pk, start=start, end=start)
        if allowed:
            assert save_absence(**kwargs).start == start
        else:
            with pytest.raises(ValidationError):
                save_absence(**kwargs)


@pytest.mark.parametrize(
    "now,start",
    [
        (datetime(2026, 12, 31, 23, 30, tzinfo=dt_timezone.utc), date(2027, 1, 15)),
        (datetime(2026, 3, 28, 23, 30, tzinfo=dt_timezone.utc), date(2026, 4, 12)),
        (datetime(2026, 10, 24, 23, 30, tzinfo=dt_timezone.utc), date(2026, 11, 8)),
    ],
)
def test_prague_date_across_midnight_year_and_dst(world, now, start):
    from datetime import timedelta

    from calendar_app.services import save_absence

    with patch("django.utils.timezone.now", return_value=now):
        with pytest.raises(ValidationError):
            save_absence(
                actor=world["person"],
                user_id=world["person"].pk,
                start=start - timedelta(days=1),
                end=start,
            )
        assert (
            save_absence(
                actor=world["person"], user_id=world["person"].pk, start=start, end=start
            ).start
            == start
        )


def test_edit_rechecks_notice_and_cancel_allowed(world):
    from calendar_app.services import delete_absence, save_absence

    with patch("django.utils.timezone.localdate", return_value=date(2026, 10, 1)):
        absence = save_absence(
            actor=world["person"],
            user_id=world["person"].pk,
            start=date(2026, 11, 1),
            end=date(2026, 11, 2),
        )
    with patch("django.utils.timezone.localdate", return_value=date(2026, 10, 25)):
        with pytest.raises(ValidationError):
            save_absence(
                actor=world["person"],
                user_id=world["person"].pk,
                start=absence.start,
                end=date(2026, 11, 3),
                absence_id=absence.pk,
            )
        delete_absence(actor=world["person"], absence_id=absence.pk)
    assert not type(absence).objects.exists()


def test_overlap_permissions_and_manager_no_override(world, client):
    from calendar_app.services import save_absence

    with patch("django.utils.timezone.localdate", return_value=date(2026, 10, 1)):
        with pytest.raises(PermissionDenied):
            save_absence(
                actor=world["other"],
                user_id=world["person"].pk,
                start=date(2026, 11, 1),
                end=date(2026, 11, 2),
            )
        with pytest.raises(ValidationError):
            save_absence(
                actor=world["manager"],
                user_id=world["person"].pk,
                start=date(2026, 10, 2),
                end=date(2026, 10, 2),
            )
        a = save_absence(
            actor=world["person"],
            user_id=world["person"].pk,
            start=date(2026, 11, 1),
            end=date(2026, 11, 2),
        )
        with pytest.raises(ValidationError):
            save_absence(
                actor=world["person"],
                user_id=world["person"].pk,
                start=date(2026, 11, 2),
                end=date(2026, 11, 3),
            )
    client.force_login(world["other"])
    assert client.get(f"/calendar/{a.pk}/edit/").status_code == 403
