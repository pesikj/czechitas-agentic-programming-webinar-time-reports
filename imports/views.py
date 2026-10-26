from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from common.permissions import require_manager

from .forms import ConfirmForm, MappingForm, UploadForm
from .models import ImportBatch
from .services import _access, confirm_batch, map_batch, upload_batch


@login_required
def upload(request):
    require_manager(request.user)
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            batch = upload_batch(
                actor=request.user,
                file=form.cleaned_data["file"],
                sheet=form.cleaned_data["sheet"] or None,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("import_mapping", pk=batch.pk)
    return render(
        request,
        "imports/upload.html",
        {"form": form, "batches": ImportBatch.objects.filter(owner=request.user)[:10]},
    )


@login_required
def mapping(request, pk):
    require_manager(request.user)
    batch = get_object_or_404(ImportBatch, pk=pk)
    try:
        _access(request.user, batch)
    except ValidationError as exc:
        return render(request, "imports/expired.html", {"errors": exc.messages}, status=400)
    form = MappingForm(
        request.POST or None, headers=batch.table["headers"], initial=batch.mapping or None
    )
    if request.method == "POST" and form.is_valid():
        try:
            map_batch(actor=request.user, batch_id=pk, mapping=form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return redirect("import_preview", pk=pk)
    return render(
        request,
        "imports/mapping.html",
        {"form": form, "batch": batch, "sample": batch.table["rows"][:5]},
    )


@login_required
def preview(request, pk):
    require_manager(request.user)
    batch = get_object_or_404(ImportBatch, pk=pk)
    try:
        _access(request.user, batch, allow_completed=True)
    except ValidationError as exc:
        return render(request, "imports/expired.html", {"errors": exc.messages}, status=400)
    if batch.status == "completed":
        return render(request, "imports/result.html", {"result": batch.result})
    if batch.status != "ready":
        return redirect("import_mapping", pk=pk)
    form = ConfirmForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            result = confirm_batch(
                actor=request.user,
                batch_id=pk,
                accept_duplicates=form.cleaned_data["accept_duplicates"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            return render(request, "imports/result.html", {"result": result})
    return render(
        request,
        "imports/preview.html",
        {"batch": batch, "form": form, "rows": batch.rows[:100], "row_count": len(batch.rows)},
    )


@login_required
def example(request):
    from django.http import HttpResponse

    require_manager(request.user)
    response = HttpResponse(
        "\ufeffDatum;Externista;Projekt;Hodiny;Popis\n2026-09-01;jana;WEB;1,5;Analýza požadavků\n",
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="vzor-vykazu.csv"'
    return response
