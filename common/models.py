from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    object_type = models.CharField(max_length=60)
    object_id = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)


def audit(actor, action, obj, **metadata):
    AuditEvent.objects.create(
        actor=actor,
        action=action,
        object_type=obj._meta.label,
        object_id=str(obj.pk),
        metadata=metadata,
    )


class RateBucket(models.Model):
    key = models.CharField(max_length=64)
    window = models.BigIntegerField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["key", "window"], name="unique_rate_window")]
