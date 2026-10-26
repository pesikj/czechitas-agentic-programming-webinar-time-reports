from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Absence(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    start = models.DateField("Od")
    end = models.DateField("Do včetně")

    class Meta:
        ordering = ["start", "user__username"]
        constraints = [
            models.CheckConstraint(condition=Q(end__gte=F("start")), name="absence_dates_order")
        ]
