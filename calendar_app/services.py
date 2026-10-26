from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from common.locking import lock_person
from common.models import audit
from common.permissions import require_owner_or_manager

from .models import Absence


def validate_absence_dates(*, start, end, today):
    earliest = today + timedelta(days=14)
    if start < earliest:
        raise ValidationError(
            f"Nepřítomnost je nutné zadat alespoň 14 dní předem. Nejbližší začátek je {earliest:%d.%m.%Y}."
        )
    if end < start:
        raise ValidationError("Konec nepřítomnosti nesmí předcházet začátku.")


@transaction.atomic
def save_absence(*, actor, user_id, start, end, absence_id=None):
    require_owner_or_manager(actor, user_id)
    lock_person(user_id)
    if absence_id:
        obj = Absence.objects.get(pk=absence_id)
        require_owner_or_manager(actor, obj.user_id)
        if obj.user_id != user_id:
            raise PermissionDenied
    else:
        obj = Absence(user_id=user_id)
    validate_absence_dates(start=start, end=end, today=timezone.localdate())
    if (
        Absence.objects.filter(user_id=user_id, start__lte=end, end__gte=start)
        .exclude(pk=absence_id)
        .exists()
    ):
        raise ValidationError("V tomto období již máte zadanou nepřítomnost.")
    obj.start = start
    obj.end = end
    obj.full_clean()
    obj.save()
    audit(actor, "absence.save", obj)
    return obj


@transaction.atomic
def delete_absence(*, actor, absence_id):
    obj = Absence.objects.get(pk=absence_id)
    require_owner_or_manager(actor, obj.user_id)
    lock_person(obj.user_id)
    # Reload after taking the same lock used by updates.
    obj = Absence.objects.get(pk=absence_id)
    audit(actor, "absence.cancel", obj)
    obj.delete()
