from django.conf import settings
from django.db import models
from django.db.models import Q


class MonthlyReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    month = models.DateField("Měsíc")
    status = models.CharField(
        max_length=12,
        choices=[("draft", "Rozpracovaný"), ("submitted", "Odeslaný")],
        default="draft",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "month"], name="unique_person_month"),
            models.CheckConstraint(condition=Q(month__day=1), name="report_month_first"),
        ]
        ordering = ["-month", "user__username"]


class TimeEntry(models.Model):
    report = models.ForeignKey(MonthlyReport, on_delete=models.PROTECT, related_name="entries")
    assignment = models.ForeignKey("contracts.Assignment", on_delete=models.PROTECT)
    date = models.DateField("Datum")
    minutes = models.PositiveIntegerField("Minuty")
    description = models.CharField("Popis práce", max_length=1000, blank=True)
    rate_snapshot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["date", "pk"]
        constraints = [
            models.CheckConstraint(condition=Q(minutes__gt=0), name="entry_minutes_positive")
        ]
