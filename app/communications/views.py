from accounts.authorization import PERM_REPAIR_ORDERS_VIEW, app_permission_required
from accounts.policies import can_add_communication_for_repair_order, require_policy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from repair_orders.models import RepairOrder

from .forms import CommunicationEntryForm


@app_permission_required(PERM_REPAIR_ORDERS_VIEW)
def communication_create(request, repair_order_pk):
    repair_order = get_object_or_404(
        RepairOrder.objects.select_related("customer", "vehicle", "assigned_to"),
        pk=repair_order_pk,
    )
    require_policy(can_add_communication_for_repair_order(request.user, repair_order))

    if request.method == "POST":
        form = CommunicationEntryForm(request.POST)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.repair_order = repair_order
            entry.created_by = request.user
            entry.save()
            messages.success(request, "Communication entry added.")
            return redirect("repair_orders:detail", pk=repair_order.pk)
    else:
        form = CommunicationEntryForm(initial={"occurred_at": timezone.now()})

    return render(
        request,
        "communications/communication_form.html",
        {
            "form": form,
            "ro": repair_order,
        },
    )
