from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.authorization import (
    PERM_REPAIR_ORDERS_MANAGE,
    PERM_REPAIR_ORDERS_VIEW,
    app_permission_required,
)
from core.document_numbers import generate_estimate_number
from repair_orders.models import RepairOrder

from .forms import EstimateForm, EstimateLineItemForm
from .models import Estimate, EstimateLineItem


@app_permission_required(PERM_REPAIR_ORDERS_VIEW)
def estimate_detail(request, pk):
    estimate = get_object_or_404(
        Estimate.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
            "parent_estimate",
            "created_by",
            "updated_by",
        ),
        pk=pk,
    )
    line_items = list(estimate.line_items.all())
    supplements = list(
        estimate.supplements.order_by("-updated_at", "-id")
    )
    return render(request, "estimates/estimate_detail.html", {
        "estimate": estimate,
        "ro": estimate.repair_order,
        "line_items": line_items,
        "supplements": supplements,
        "has_line_items": bool(line_items),
    })


@app_permission_required(PERM_REPAIR_ORDERS_VIEW)
def estimate_print(request, pk):
    estimate = get_object_or_404(
        Estimate.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
            "parent_estimate",
        ),
        pk=pk,
    )
    line_items = list(estimate.line_items.all())
    return render(request, "estimates/estimate_print.html", {
        "estimate": estimate,
        "ro": estimate.repair_order,
        "line_items": line_items,
        "has_line_items": bool(line_items),
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
        "supplement_parent": None,
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
        "supplement_parent": None,
        "mode": "edit",
        "title": f"Edit Estimate {estimate.estimate_number}",
        "submit_label": "Save Changes",
    })


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def supplement_create(request, pk):
    parent = get_object_or_404(
        Estimate.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
        ),
        pk=pk,
    )
    ro = parent.repair_order

    if request.method == "POST":
        form = EstimateForm(request.POST)
        if form.is_valid():
            supplement = form.save(commit=False)
            supplement.repair_order = ro
            supplement.kind = Estimate.Kind.SUPPLEMENT
            supplement.parent_estimate = parent
            supplement.estimate_number = generate_estimate_number()
            supplement.created_by = request.user
            supplement.updated_by = request.user
            supplement.save()
            messages.success(
                request,
                f"Supplement {supplement.estimate_number} created for "
                f"estimate {parent.estimate_number}.",
            )
            return redirect("estimates:detail", pk=supplement.pk)
    else:
        # Seed insurance/claim context from the parent as starting values.
        form = EstimateForm(initial={
            "insurance_company": parent.insurance_company,
            "claim_number": parent.claim_number,
            "deductible": parent.deductible,
        })

    return render(request, "estimates/estimate_form.html", {
        "form": form,
        "ro": ro,
        "estimate": None,
        "supplement_parent": parent,
        "mode": "create",
        "title": f"New Supplement for Estimate {parent.estimate_number}",
        "submit_label": "Create Supplement",
    })


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def line_item_create(request, estimate_pk):
    estimate = get_object_or_404(
        Estimate.objects.select_related("repair_order"),
        pk=estimate_pk,
    )

    if request.method == "POST":
        form = EstimateLineItemForm(request.POST)
        if form.is_valid():
            line_item = form.save(commit=False)
            line_item.estimate = estimate
            line_item.save()  # full_clean + recalculate estimate total
            messages.success(request, "Estimate line item added.")
            return redirect("estimates:detail", pk=estimate.pk)
    else:
        form = EstimateLineItemForm()

    return render(request, "estimates/estimate_line_item_form.html", {
        "form": form,
        "estimate": estimate,
        "ro": estimate.repair_order,
        "line_item": None,
        "mode": "create",
        "title": f"Add Line Item to Estimate {estimate.estimate_number}",
        "submit_label": "Add Line Item",
    })


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def line_item_edit(request, pk):
    line_item = get_object_or_404(
        EstimateLineItem.objects.select_related(
            "estimate",
            "estimate__repair_order",
        ),
        pk=pk,
    )
    estimate = line_item.estimate

    if request.method == "POST":
        form = EstimateLineItemForm(request.POST, instance=line_item)
        if form.is_valid():
            form.save()  # recalculates estimate total
            messages.success(request, "Estimate line item updated.")
            return redirect("estimates:detail", pk=estimate.pk)
    else:
        form = EstimateLineItemForm(instance=line_item)

    return render(request, "estimates/estimate_line_item_form.html", {
        "form": form,
        "estimate": estimate,
        "ro": estimate.repair_order,
        "line_item": line_item,
        "mode": "edit",
        "title": f"Edit Line Item for Estimate {estimate.estimate_number}",
        "submit_label": "Save Changes",
    })


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def line_item_delete(request, pk):
    line_item = get_object_or_404(
        EstimateLineItem.objects.select_related("estimate"),
        pk=pk,
    )
    estimate = line_item.estimate

    if request.method != "POST":
        return redirect("estimates:detail", pk=estimate.pk)

    line_item.delete()  # recalculates estimate total
    messages.success(request, "Estimate line item removed.")
    return redirect("estimates:detail", pk=estimate.pk)
