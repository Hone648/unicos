from accounts.authorization import (
    PERM_REPAIR_ORDERS_MANAGE,
    PERM_REPAIR_ORDERS_VIEW,
    app_permission_required,
)
from accounts.policies import (
    can_delete_attachment,
    can_upload_attachment_for_repair_order,
    can_view_attachment,
    require_policy,
)
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from repair_orders.models import RepairOrder

from .forms import AttachmentForm
from .models import Attachment


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def attachment_upload(request, repair_order_pk):
    ro = get_object_or_404(
        RepairOrder.objects.select_related("customer", "vehicle"),
        pk=repair_order_pk,
    )
    require_policy(can_upload_attachment_for_repair_order(request.user, ro))

    if request.method == "POST":
        form = AttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.repair_order = ro
            attachment.uploaded_by = request.user
            uploaded_file = request.FILES["file"]
            attachment.original_filename = uploaded_file.name
            attachment.content_type = getattr(uploaded_file, "content_type", "")
            attachment.size_bytes = uploaded_file.size
            attachment.save()
            messages.success(request, f"Attachment '{attachment.original_filename}' uploaded.")
            return redirect("repair_orders:detail", pk=ro.pk)
    else:
        form = AttachmentForm()

    return render(
        request,
        "attachments/attachment_form.html",
        {
            "form": form,
            "ro": ro,
        },
    )


@app_permission_required(PERM_REPAIR_ORDERS_VIEW)
def attachment_download(request, pk):
    attachment = get_object_or_404(
        Attachment.objects.select_related("repair_order"),
        pk=pk,
    )
    require_policy(can_view_attachment(request.user, attachment))

    try:
        return FileResponse(
            attachment.file.open("rb"),
            as_attachment=True,
            filename=attachment.original_filename,
        )
    except FileNotFoundError:
        raise Http404("Attachment file not found.")


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
@require_POST
def attachment_delete(request, pk):
    attachment = get_object_or_404(
        Attachment.objects.select_related("repair_order"),
        pk=pk,
    )
    require_policy(can_delete_attachment(request.user, attachment))

    ro_pk = attachment.repair_order_id
    filename = attachment.original_filename
    try:
        attachment.file.delete(save=False)
    except FileNotFoundError:
        pass
    attachment.delete()
    messages.success(request, f"Attachment '{filename}' deleted.")
    return redirect("repair_orders:detail", pk=ro_pk)
