import uuid

from django.conf import settings
from django.db import models


class ImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    filename = models.CharField(max_length=255)
    fingerprint = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=12, default="mapping")
    table = models.JSONField(default=dict)
    mapping = models.JSONField(default=dict)
    rows = models.JSONField(default=list)
    errors = models.JSONField(default=list)
    duplicates = models.JSONField(default=list)
    result = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]
