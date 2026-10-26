from collections import defaultdict
from dataclasses import dataclass

from django.core.exceptions import ValidationError

from contracts.services import terms_for


@dataclass
class ReportIssue:
    code: str
    message: str
    date: object = None
    project: object = None
    total: int = 0
    limit: int = 0

    @property
    def excess(self):
        return max(0, self.total - self.limit)


def validate_report(report, historical=False, entries=None):
    issues = []
    days = defaultdict(int)
    projects = defaultdict(int)
    assignments = {}
    if entries is None:
        entries = list(report.entries.select_related("assignment__project", "assignment__user"))
    if not entries:
        return [ReportIssue("empty", "Prázdný výkaz nelze odeslat.")]
    for e in entries:
        a = e.assignment
        if e.date.replace(day=1) != report.month or e.minutes <= 0 or a.user_id != report.user_id:
            issues.append(
                ReportIssue("invalid", "Položka nepatří do tohoto měsíce nebo uživateli.")
            )
            continue
        if e.date < a.start or (a.end and e.date > a.end):
            issues.append(
                ReportIssue(
                    "assignment",
                    f"{e.date:%d.%m.%Y}: neplatné období přiřazení k projektu {a.project.code}.",
                )
            )
        if not historical and (not a.is_active or not a.project.is_active):
            issues.append(
                ReportIssue("inactive", f"Projekt {a.project.code} nebo přiřazení není aktivní.")
            )
        days[e.date] += e.minutes
        projects[a.pk] += e.minutes
        assignments[a.pk] = a
    for day, total in days.items():
        if total > 480:
            issues.append(
                ReportIssue(
                    "daily",
                    f"{day:%d.%m.%Y}: vykázáno {total} minut, limit 480 minut, překročení {total - 480} minut.",
                    date=day,
                    total=total,
                    limit=480,
                )
            )
    for aid, total in projects.items():
        a = assignments[aid]
        try:
            terms = terms_for(a, report.month)
        except ValidationError as exc:
            issues.extend(ReportIssue("terms", m) for m in exc.messages)
            continue
        if total > terms.monthly_limit_minutes:
            limit = terms.monthly_limit_minutes
            issues.append(
                ReportIssue(
                    "monthly",
                    f"{a.project.code}: vykázáno {total} minut za měsíc, limit {limit} minut, překročení {total - limit} minut.",
                    project=a.project,
                    total=total,
                    limit=limit,
                )
            )
    return issues
