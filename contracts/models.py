from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class Project(models.Model):
    code = models.CharField("Kód projektu", max_length=40, unique=True)
    name = models.CharField("Název", max_length=160)
    is_active = models.BooleanField("Aktivní", default=True)

    def __str__(self):
        return f"{self.code} · {self.name}"


class Assignment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    start = models.DateField("Platí od")
    end = models.DateField("Platí do", blank=True, null=True)
    is_active = models.BooleanField("Aktivní", default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "project"], name="unique_person_project"),
            models.CheckConstraint(
                condition=Q(end__isnull=True) | Q(end__gte=F("start")),
                name="assignment_dates_order",
            ),
        ]

    def clean(self):
        if self.end and self.start and self.end < self.start:
            raise ValidationError("Konec přiřazení musí být po začátku.")

    def __str__(self):
        return f"{self.user} → {self.project}"


class ContractTerms(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.PROTECT, related_name="terms")
    start_month = models.DateField("Od měsíce (první den)")
    end_month = models.DateField("Do měsíce včetně (první den)", blank=True, null=True)
    hourly_rate = models.DecimalField(
        "Sazba Kč/h", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))]
    )
    monthly_limit_minutes = models.PositiveIntegerField(
        "Měsíční limit v minutách", validators=[MinValueValidator(1)]
    )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(hourly_rate__gte=0), name="rate_nonnegative"),
            models.CheckConstraint(condition=Q(monthly_limit_minutes__gt=0), name="limit_positive"),
            models.CheckConstraint(
                condition=Q(end_month__isnull=True) | Q(end_month__gte=F("start_month")),
                name="terms_dates_order",
            ),
        ]

    def clean(self):
        if not self.start_month:
            return
        if self.start_month.day != 1 or (self.end_month and self.end_month.day != 1):
            raise ValidationError(
                "Podmínky začínají a končí prvním dnem měsíce; koncový měsíc je zahrnut."
            )
        if self.end_month and self.end_month < self.start_month:
            raise ValidationError("Koncový měsíc musí být po počátečním.")
        others = ContractTerms.objects.filter(assignment_id=self.assignment_id).exclude(pk=self.pk)
        others = others.filter(start_month__lte=self.end_month or date.max).filter(
            Q(end_month__isnull=True) | Q(end_month__gte=self.start_month)
        )
        if others.exists():
            raise ValidationError("Smluvní podmínky se v tomto období překrývají.")

    def __str__(self):
        return f"{self.assignment} od {self.start_month:%m/%Y}"
