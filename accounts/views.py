from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from common.models import audit
from common.permissions import require_manager

from .forms import AccountForm
from .models import User
from .services import issue_setup_link


@login_required
def accounts(request):
    require_manager(request.user)
    return render(
        request, "accounts/list.html", {"people": User.objects.order_by("last_name", "username")}
    )


@login_required
@transaction.atomic
def account_form(request, pk=None):
    require_manager(request.user)
    user = get_object_or_404(User.objects.select_for_update(), pk=pk) if pk else User()
    form = AccountForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        if user.pk == request.user.pk and (
            not form.cleaned_data["is_active"] or not form.cleaned_data["is_staff"]
        ):
            form.add_error(None, "Vlastní správcovský přístup nelze odebrat.")
        else:
            new = not user.pk
            if new:
                user.set_unusable_password()
            form.save()
            audit(request.user, "account.save", user)
            messages.success(
                request, "Účet byl uložen. Pro nový účet vytvořte odkaz pro nastavení hesla."
            )
            return redirect("accounts")
    return render(
        request,
        "form.html",
        {"form": form, "title": "Účet externisty" if not pk else "Upravit účet"},
    )


@login_required
@require_POST
def setup_link(request, pk):
    require_manager(request.user)
    user = get_object_or_404(User, pk=pk)
    return render(
        request,
        "accounts/setup_link.html",
        {"person": user, "link": issue_setup_link(actor=request.user, user=user, request=request)},
    )
