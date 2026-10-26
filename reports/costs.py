from collections import OrderedDict
from decimal import ROUND_HALF_UP, Decimal, localcontext

from django.core.exceptions import ValidationError

from common.permissions import require_manager
from contracts.services import terms_for

from .models import TimeEntry


def monthly_costs(*, actor, month):
    require_manager(actor)
    rows = OrderedDict()
    with localcontext() as ctx:
        ctx.prec = 40
        for entry in (
            TimeEntry.objects.filter(report__month=month)
            .select_related("report__user", "assignment__project")
            .order_by("assignment__project__code", "report__user__username")
        ):
            project = entry.assignment.project
            row = rows.setdefault(
                project.pk,
                {
                    "project": project,
                    "code": project.code,
                    "minutes": 0,
                    "draft_minutes": 0,
                    "cost": Decimal(0),
                    "estimate": Decimal(0),
                    "incomplete": False,
                    "people": {},
                },
            )
            person = row["people"].setdefault(
                entry.report.user_id,
                {
                    "user": entry.report.user,
                    "minutes": 0,
                    "draft_minutes": 0,
                    "cost": Decimal(0),
                    "estimate": Decimal(0),
                    "incomplete": False,
                },
            )
            submitted = entry.report.status == "submitted"
            cost_key = "cost" if submitted else "estimate"
            minutes_key = "minutes" if submitted else "draft_minutes"
            rate = entry.rate_snapshot
            if rate is None and not submitted:
                try:
                    rate = terms_for(entry.assignment, month).hourly_rate
                except ValidationError:
                    pass
            row[minutes_key] += entry.minutes
            person[minutes_key] += entry.minutes
            if rate is None:
                row["incomplete"] = person["incomplete"] = True
            else:
                amount = Decimal(entry.minutes) * rate / 60
                row[cost_key] += amount
                person[cost_key] += amount
        for row in rows.values():
            for data in [row, *row["people"].values()]:
                for key in ["cost", "estimate"]:
                    data[key] = data[key].quantize(Decimal(".01"), rounding=ROUND_HALF_UP)
            row["people"] = list(row["people"].values())
    return list(rows.values())
