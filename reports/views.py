from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from common.permissions import require_manager, require_owner_or_manager

from .forms import EntryForm, MonthForm, ReasonForm
from .models import MonthlyReport, TimeEntry
from .services import (
    delete_entry,
    get_or_create_report,
    reopen_report,
    reprice_report,
    save_entry,
    submit_report,
)
from .validation import validate_report


def month_from_request(request):
    form = MonthForm(request.GET or {"month": timezone.localdate().strftime("%Y-%m")})
    return (
        form.cleaned_data["month"] if form.is_valid() else timezone.localdate().replace(day=1)
    ), form


@login_required
def index(request):
    month, form = month_from_request(request)
    reports = MonthlyReport.objects.filter(month=month).select_related("user")
    if not request.user.is_staff:
        reports = reports.filter(user=request.user)
    rows = [{"report": r, "minutes": sum(e.minutes for e in r.entries.all())} for r in reports]
    return render(request, "reports/list.html", {"rows": rows, "month_form": form, "month": month})


@login_required
@require_POST
def create(request):
    form = MonthForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Vyberte platný měsíc.")
        return redirect("reports")
    report = get_or_create_report(
        actor=request.user, user_id=request.user.pk, month=form.cleaned_data["month"]
    )
    return redirect("report_detail", pk=report.pk)


@login_required
def detail(request, pk):
    report = get_object_or_404(MonthlyReport.objects.select_related("user"), pk=pk)
    require_owner_or_manager(request.user, report.user_id)
    entries = report.entries.select_related("assignment__project")
    return render(
        request,
        "reports/detail.html",
        {
            "report": report,
            "entries": entries,
            "total_hours": Decimal(sum(e.minutes for e in entries)) / 60,
            "issues": validate_report(report) if report.status == "draft" else [],
        },
    )


@login_required
def entry_form(request, pk, entry_id=None):
    report = get_object_or_404(MonthlyReport, pk=pk)
    require_owner_or_manager(request.user, report.user_id)
    if report.status != "draft":
        messages.error(request, "Odeslaný výkaz je zamčený.")
        return redirect("report_detail", pk=pk)
    entry = get_object_or_404(TimeEntry, pk=entry_id, report=report) if entry_id else None
    initial = {"date": report.month, "assignment": entry.assignment_id if entry else None}
    if entry:
        initial.update(
            date=entry.date, hours=Decimal(entry.minutes) / 60, description=entry.description
        )
    form = EntryForm(request.POST or None, user_id=report.user_id, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            save_entry(
                actor=request.user,
                report_id=pk,
                assignment_id=form.cleaned_data["assignment"].pk,
                date=form.cleaned_data["date"],
                minutes=form.cleaned_data["hours"],
                description=form.cleaned_data["description"],
                entry_id=entry_id,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Práce byla uložena.")
            return redirect("report_detail", pk=pk)
    return render(
        request, "form.html", {"form": form, "title": "Upravit práci" if entry else "Zapsat práci"}
    )


@login_required
@require_POST
def entry_delete(request, entry_id):
    entry = get_object_or_404(TimeEntry, pk=entry_id)
    try:
        delete_entry(actor=request.user, entry_id=entry_id)
    except ValidationError as exc:
        for m in exc.messages:
            messages.error(request, m)
    return redirect("report_detail", pk=entry.report_id)


@login_required
@require_POST
def submit(request, pk):
    get_object_or_404(MonthlyReport, pk=pk)
    try:
        submit_report(actor=request.user, report_id=pk)
    except ValidationError as exc:
        for m in exc.messages:
            messages.error(request, m)
    else:
        messages.success(request, "Výkaz byl odeslán a zamčen.")
    return redirect("report_detail", pk=pk)


@login_required
def correction(request, pk, operation):
    require_manager(request.user)
    get_object_or_404(MonthlyReport, pk=pk)
    form = ReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            (reopen_report if operation == "reopen" else reprice_report)(
                actor=request.user, report_id=pk, reason=form.cleaned_data["reason"]
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Změna byla provedena a zaznamenána.")
            return redirect("report_detail", pk=pk)
    return render(
        request,
        "form.html",
        {
            "form": form,
            "title": "Vrátit k opravě" if operation == "reopen" else "Přepočítat historické sazby",
        },
    )


@login_required
def costs(request):
    from .costs import monthly_costs

    require_manager(request.user)
    month, form = month_from_request(request)
    rows = monthly_costs(actor=request.user, month=month)
    return render(
        request,
        "reports/costs.html",
        {
            "rows": rows,
            "month": month,
            "month_form": form,
            "total_cost": sum(r["cost"] for r in rows),
            "total_minutes": sum(r["minutes"] for r in rows),
            "total_estimate": sum(r["estimate"] for r in rows),
        },
    )
