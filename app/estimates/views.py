from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.authorization import (
    PERM_BILLING_MANAGE,
    PERM_REPAIR_ORDERS_MANAGE,
    PERM_REPAIR_ORDERS_VIEW,
    app_permission_required,
)
from accounts.policies import (
    can_convert_estimate_to_invoice,
    can_manage_estimate,
    can_manage_estimate_for_repair_order,
    can_view_estimate,
    require_policy,
)
from billing.services import (
    EstimateInvoiceConversionBlocked,
    convert_estimate_to_invoice,
    estimate_can_convert_to_invoice,
)
from core.document_numbers import generate_estimate_number
from repair_orders.models import RepairOrder

from .forms import EstimateApprovalForm, EstimateForm, EstimateLineItemForm
from .models import Estimate, EstimateLineItem
from .services import (
    EstimateStatusTransitionBlocked,
    estimate_is_editable,
    get_available_estimate_status_transitions,
    transition_estimate_status,
)


_STATUS_ACTION_LABELS = {
    Estimate.Status.SUBMITTED: "Submit Estimate",
    Estimate.Status.APPROVED: "Approve Estimate",
    Estimate.Status.DECLINED: "Decline Estimate",
    Estimate.Status.EXPIRED: "Expire Estimate",
}


def _estimate_locked_message(estimate):
    return (
        f"Estimate {estimate.estimate_number} is "
        f"{estimate.get_status_display().lower()} and cannot be edited."
    )


def _status_action_choices(estimate):
    available_statuses = get_available_estimate_status_transitions(estimate)
    return [
        (status, _STATUS_ACTION_LABELS[status])
        for status in _STATUS_ACTION_LABELS
        if status in available_statuses
    ]


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
    require_policy(can_view_estimate(request.user, estimate))
    line_items = list(estimate.line_items.all())
    supplements = list(
        estimate.supplements.order_by("-updated_at", "-id")
    )
    converted_invoice = estimate.converted_invoices.first()
    status_action_choices = _status_action_choices(estimate)
    can_manage = can_manage_estimate(request.user, estimate)
    can_convert = (
        can_convert_estimate_to_invoice(request.user, estimate)
        and estimate_can_convert_to_invoice(estimate)
    )
    return render(request, "estimates/estimate_detail.html", {
        "estimate": estimate,
        "ro": estimate.repair_order,
        "line_items": line_items,
        "supplements": supplements,
        "has_line_items": bool(line_items),
        "is_editable": estimate_is_editable(estimate),
        "status_action_choices": status_action_choices,
        "approval_form": EstimateApprovalForm()
        if can_manage
        and Estimate.Status.APPROVED in {status for status, _label in status_action_choices}
        else None,
        "can_manage_estimate": can_manage,
        "can_convert_to_invoice": can_convert,
        "converted_invoice": converted_invoice,
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
    require_policy(can_view_estimate(request.user, estimate))
    line_items = list(estimate.line_items.all())
    return render(request, "estimates/estimate_print.html", {
        "estimate": estimate,
        "ro": estimate.repair_order,
        "line_items": line_items,
        "has_line_items": bool(line_items),
    })


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
@require_POST
def estimate_status_update(request, pk):
    estimate = get_object_or_404(Estimate, pk=pk)
    require_policy(can_manage_estimate(request.user, estimate))
    new_status = request.POST.get("status", "").strip()
    approval_data = None

    if new_status == Estimate.Status.APPROVED:
        form = EstimateApprovalForm(request.POST)
        if not form.is_valid():
            messages.error(
                request,
                "Approval source and approval contact name are required before "
                "approving an estimate.",
            )
            return redirect("estimates:detail", pk=estimate.pk)
        approval_data = form.cleaned_data

    try:
        transition_estimate_status(
            estimate,
            new_status,
            updated_by=request.user,
            approval_data=approval_data,
        )
    except EstimateStatusTransitionBlocked as exc:
        messages.error(request, str(exc))
        return redirect("estimates:detail", pk=estimate.pk)

    messages.success(
        request,
        f"Estimate {estimate.estimate_number} marked "
        f"{estimate.get_status_display().lower()}.",
    )
    return redirect("estimates:detail", pk=estimate.pk)


@app_permission_required(PERM_BILLING_MANAGE)
@require_POST
def estimate_convert_to_invoice(request, pk):
    estimate = get_object_or_404(
        Estimate.objects.select_related("repair_order"),
        pk=pk,
    )
    require_policy(can_convert_estimate_to_invoice(request.user, estimate))

    try:
        invoice = convert_estimate_to_invoice(estimate, created_by=request.user)
    except EstimateInvoiceConversionBlocked as exc:
        messages.error(request, str(exc))
        return redirect("estimates:detail", pk=estimate.pk)

    messages.success(
        request,
        f"Invoice {invoice.invoice_number} created from estimate "
        f"{estimate.estimate_number}.",
    )
    return redirect("billing:invoice_detail", pk=invoice.pk)


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def estimate_create(request, repair_order_pk):
    ro = get_object_or_404(
        RepairOrder.objects.select_related("customer", "vehicle"),
        pk=repair_order_pk,
    )
    require_policy(can_manage_estimate_for_repair_order(request.user, ro))

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
    require_policy(can_manage_estimate(request.user, estimate))

    if not estimate_is_editable(estimate):
        messages.error(request, _estimate_locked_message(estimate))
        return redirect("estimates:detail", pk=estimate.pk)

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
    require_policy(can_manage_estimate(request.user, parent))

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
    require_policy(can_manage_estimate(request.user, estimate))

    if not estimate_is_editable(estimate):
        messages.error(request, _estimate_locked_message(estimate))
        return redirect("estimates:detail", pk=estimate.pk)

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
    require_policy(can_manage_estimate(request.user, estimate))

    if not estimate_is_editable(estimate):
        messages.error(request, _estimate_locked_message(estimate))
        return redirect("estimates:detail", pk=estimate.pk)

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
    require_policy(can_manage_estimate(request.user, estimate))

    if not estimate_is_editable(estimate):
        messages.error(request, _estimate_locked_message(estimate))
        return redirect("estimates:detail", pk=estimate.pk)

    if request.method != "POST":
        return redirect("estimates:detail", pk=estimate.pk)

    line_item.delete()  # recalculates estimate total
    messages.success(request, "Estimate line item removed.")
    return redirect("estimates:detail", pk=estimate.pk)
