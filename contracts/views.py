from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from common.permissions import require_manager

from .forms import AssignmentForm, ProjectForm, TermsForm
from .models import Assignment, ContractTerms, Project
from .services import save_assignment, save_terms


@login_required
def overview(request):
    require_manager(request.user)
    return render(
        request,
        "contracts/overview.html",
        {
            "projects": Project.objects.order_by("code"),
            "assignments": Assignment.objects.select_related("user", "project").order_by(
                "project__code", "user__username"
            ),
            "terms": ContractTerms.objects.select_related(
                "assignment__user", "assignment__project"
            ).order_by("-start_month"),
        },
    )


@login_required
def contract_form(request, kind, pk=None):
    require_manager(request.user)
    if kind not in {"project", "assignment", "terms"}:
        raise Http404
    model, form_class, title = {
        "project": (Project, ProjectForm, "Projekt"),
        "assignment": (Assignment, AssignmentForm, "Přiřazení externisty"),
        "terms": (ContractTerms, TermsForm, "Smluvní podmínky"),
    }[kind]
    obj = get_object_or_404(model, pk=pk) if pk else model()
    form = form_class(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        try:
            if kind == "terms":
                save_terms(actor=request.user, terms=form.instance)
            elif kind == "assignment":
                save_assignment(actor=request.user, assignment=form.instance)
            else:
                form.save()
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Změny byly uloženy.")
            return redirect("contracts")
    return render(request, "form.html", {"form": form, "title": title})
