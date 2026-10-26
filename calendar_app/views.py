import calendar
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import User
from common.permissions import require_owner_or_manager
from reports.views import month_from_request

from .forms import AbsenceForm
from .models import Absence
from .services import delete_absence, save_absence


@login_required
def calendar_view(request):
    month, form = month_from_request(request)
    # Keep navigation within datetime's range even for hostile query parameters.
    if month.year < 2 or month.year > 9998:
        month = timezone.localdate().replace(day=1)
    last = month.replace(day=calendar.monthrange(month.year, month.month)[1])
    absences = Absence.objects.filter(start__lte=last, end__gte=month).select_related("user")
    selected = request.GET.get("person", "")
    if selected.isdigit():
        absences = absences.filter(user_id=int(selected))
    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(month.year, month.month):
        weeks.append(
            [
                {
                    "date": day,
                    "outside": day.month != month.month,
                    "absences": [a for a in absences if a.start <= day <= a.end],
                }
                for day in week
            ]
        )
    people = User.objects.filter(is_active=True) | User.objects.filter(
        absence__start__lte=last, absence__end__gte=month
    )
    return render(
        request,
        "calendar_app/calendar.html",
        {
            "month": month,
            "month_form": form,
            "weeks": weeks,
            "absences": absences,
            "people": people.distinct().order_by("last_name", "username"),
            "selected_person": selected,
            "prev_month": (month - timedelta(days=1)).replace(day=1),
            "next_month": last + timedelta(days=1),
            "earliest": timezone.localdate() + timedelta(days=14),
        },
    )


@login_required
def absence_form(request, pk=None):
    obj = get_object_or_404(Absence, pk=pk) if pk else None
    if obj:
        require_owner_or_manager(request.user, obj.user_id)
    initial = (
        {"user": obj.user_id, "start": obj.start, "end": obj.end}
        if obj
        else {
            "start": timezone.localdate() + timedelta(days=14),
            "end": timezone.localdate() + timedelta(days=14),
        }
    )
    form = AbsenceForm(request.POST or None, actor=request.user, initial=initial)
    if obj:
        form.fields["user"].disabled = True
    if request.method == "POST" and form.is_valid():
        try:
            save_absence(
                actor=request.user,
                user_id=form.cleaned_data["user"].pk,
                start=form.cleaned_data["start"],
                end=form.cleaned_data["end"],
                absence_id=pk,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Nepřítomnost byla uložena.")
            return redirect("calendar")
    return render(
        request,
        "calendar_app/form.html",
        {
            "form": form,
            "title": "Upravit nepřítomnost" if obj else "Naplánovat nepřítomnost",
            "earliest": timezone.localdate() + timedelta(days=14),
        },
    )


@login_required
@require_POST
def cancel(request, pk):
    get_object_or_404(Absence, pk=pk)
    delete_absence(actor=request.user, absence_id=pk)
    messages.success(request, "Nepřítomnost byla zrušena.")
    return redirect("calendar")
