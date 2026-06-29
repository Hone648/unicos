from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.authorization import (
    PERM_REPAIR_ORDERS_MANAGE,
    PERM_REPAIR_ORDERS_VIEW,
    app_permission_required,
)
from core.document_numbers import generate_estimate_number
from repair_orders.models import RepairOrder

from .forms import EstimateForm
from .models import Estimate


@app_permission_required(PERM_REPAIR_ORDERS_VIEW)
def estimate_detail(request, pk):
    estimate = get_object_or_404(
        Estimate.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
            "created_by",
            "updated_by",
        ),
        pk=pk,
    )
    return render(request, "estimates/estimate_detail.html", {
        "estimate": estimate,
        "ro": estimate.repair_order,
    })


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def estimate_create(request, repair_order_pk):
    ro = get_object_or_404(
        RepairOrder.objects.select_related("customer", "vehicle"),
        pk=repair_order_pk,
    )

    if request.method == "POST":
        form = EstimateForm(request.POST)
        if form.is_valid():
            estimate = form.save(commit=False)
            estimate.repair_order = ro
            estimate.estimate_number = generate_estimate_number()
            estimate.created_by = request.user
            estimate.updated_by = request.user
            estimate.save()
            messages.success(request, f"Estimate {estimate.estimate_number} created.")
            return redirect("estimates:detail", pk=estimate.pk)
    else:
        form = EstimateForm()

    return render(request, "estimates/estimate_form.html", {
        "form": form,
        "ro": ro,
        "estimate": None,
        "mode": "create",
        "title": f"New Estimate for RO {ro.repair_order_number}",
        "submit_label": "Create Estimate",
    })


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def estimate_edit(request, pk):
    estimate = get_object_or_404(
        Estimate.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
        ),
        pk=pk,
    )
    ro = estimate.repair_order

    if request.method == "POST":
        form = EstimateForm(request.POST, instance=estimate)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.updated_by = request.user
            updated.save()
            messages.success(request, f"Estimate {estimate.estimate_number} updated.")
            return redirect("estimates:detail", pk=estimate.pk)
    else:
        form = EstimateForm(instance=estimate)

    return render(request, "estimates/estimate_form.html", {
        "form": form,
        "ro": ro,
        "estimate": estimate,
        "mode": "edit",
        "title": f"Edit Estimate {estimate.estimate_number}",
        "submit_label": "Save Changes",
    })
