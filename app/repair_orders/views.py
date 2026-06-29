from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.authorization import (
    PERM_REPAIR_ORDERS_CHANGE_STATUS,
    PERM_REPAIR_ORDERS_MANAGE,
    PERM_REPAIR_ORDERS_VIEW,
    app_permission_required,
)
from core.document_numbers import generate_repair_order_number
from core.pagination import paginate_queryset, pagination_querystring

from .business_rules import is_final_repair_order_status
from .forms import RepairOrderCreateForm, RepairOrderEditForm
from .models import RepairOrder
from .services import RepairOrderStatusTransitionBlocked, transition_repair_order_status

# Status values that count as "closed" for default list filtering
_CLOSED_STATUSES = {RepairOrder.Status.CLOSED, RepairOrder.Status.CANCELED}

# All valid status values for quick lookup
_VALID_STATUSES = set(RepairOrder.Status.values)


def _repair_order_detail_context(ro):
    """Build context shared by the full detail view and HTMX partial responses."""
    history = ro.status_history.select_related("changed_by").order_by("-changed_at", "-id")
    invoice = None
    payments = []
    line_items = []
    try:
        invoice = ro.invoice
        line_items = list(invoice.line_items.order_by("id"))
        payments = list(
            invoice.payments.select_related("received_by").order_by("-payment_date", "-created_at")
        )
    except RepairOrder.invoice.RelatedObjectDoesNotExist:
        pass
    estimates = list(
        ro.estimates.select_related("created_by", "updated_by").order_by("-updated_at", "-id")
    )
    return {
        "ro": ro,
        "history": history,
        "invoice": invoice,
        "is_final_repair_order": is_final_repair_order_status(ro.status),
        "line_items": line_items,
        "payments": payments,
        "estimates": estimates,
        "status_choices": RepairOrder.Status.choices,
    }


@app_permission_required(PERM_REPAIR_ORDERS_VIEW)
def repair_order_list(request):
    qs = (
        RepairOrder.objects.select_related("customer", "vehicle", "assigned_to")
        .order_by("-opened_at", "-id")
    )

    status_filter = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()

    if status_filter == "all":
        pass  # no status filtering
    elif status_filter == "closed":
        qs = qs.filter(status=RepairOrder.Status.CLOSED)
    elif status_filter == "canceled":
        qs = qs.filter(status=RepairOrder.Status.CANCELED)
    elif status_filter in _VALID_STATUSES:
        qs = qs.filter(status=status_filter)
    else:
        # Default: exclude closed and canceled
        qs = qs.exclude(status__in=_CLOSED_STATUSES)

    if q:
        qs = qs.filter(
            Q(repair_order_number__icontains=q)
            | Q(customer__first_name__icontains=q)
            | Q(customer__last_name__icontains=q)
            | Q(customer__business_name__icontains=q)
            | Q(vehicle__vin__icontains=q)
            | Q(vehicle__make__icontains=q)
            | Q(vehicle__model__icontains=q)
            | Q(vehicle__license_plate__icontains=q)
        )

    page_obj = paginate_queryset(request, qs)
    return render(
        request,
        "repair_orders/repair_order_list.html",
        {
            "repair_orders": page_obj.object_list,
            "page_obj": page_obj,
            "pagination_query": pagination_querystring(request),
            "q": q,
            "status_filter": status_filter,
            "status_choices": RepairOrder.Status.choices,
        },
    )


@app_permission_required(PERM_REPAIR_ORDERS_VIEW)
def repair_order_detail(request, pk):
    ro = get_object_or_404(
        RepairOrder.objects.select_related(
            "customer",
            "vehicle",
            "assigned_to",
            "created_by",
            "updated_by",
        ),
        pk=pk,
    )
    return render(request, "repair_orders/repair_order_detail.html",
                  _repair_order_detail_context(ro))


@app_permission_required(PERM_REPAIR_ORDERS_CHANGE_STATUS)
def repair_order_status_update(request, pk):
    if request.method != "POST":
        return redirect("repair_orders:detail", pk=pk)

    is_htmx = request.headers.get("HX-Request") == "true"

    ro = get_object_or_404(RepairOrder, pk=pk)
    new_status = request.POST.get("new_status", "").strip()
    note = request.POST.get("note", "").strip()

    if new_status not in _VALID_STATUSES:
        messages.error(request, f"'{new_status}' is not a valid repair order status.")
        if not is_htmx:
            return redirect("repair_orders:detail", pk=pk)
        return render(request, "repair_orders/partials/_status_update_response.html",
                      _repair_order_detail_context(ro))

    if new_status == ro.status:
        messages.info(request, "Status is already set to that value — no change made.")
        if not is_htmx:
            return redirect("repair_orders:detail", pk=pk)
        return render(request, "repair_orders/partials/_status_update_response.html",
                      _repair_order_detail_context(ro))

    if not note:
        note = "Status changed from repair order workspace."

    try:
        transition_repair_order_status(ro, new_status, changed_by=request.user, note=note)
    except RepairOrderStatusTransitionBlocked as exc:
        messages.error(request, str(exc))
        if not is_htmx:
            return redirect("repair_orders:detail", pk=pk)
        return render(request, "repair_orders/partials/_status_update_response.html",
                      _repair_order_detail_context(ro))

    label = dict(RepairOrder.Status.choices).get(new_status, new_status)
    messages.success(request, f"Status updated to \"{label}\".")

    if not is_htmx:
        return redirect("repair_orders:detail", pk=pk)

    return render(request, "repair_orders/partials/_status_update_response.html",
                  _repair_order_detail_context(ro))


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def repair_order_create(request):
    if request.method == "POST":
        form = RepairOrderCreateForm(request.POST)
        if form.is_valid():
            ro = form.save(commit=False)
            ro.repair_order_number = generate_repair_order_number()
            ro.created_by = request.user
            ro.updated_by = request.user
            ro.save()
            messages.success(request, f"Repair order {ro.repair_order_number} created.")
            return redirect("repair_orders:detail", pk=ro.pk)
    else:
        form = RepairOrderCreateForm()
    return render(request, "repair_orders/repair_order_form.html", {
        "form": form,
        "mode": "create",
        "title": "New Repair Order",
        "submit_label": "Create Repair Order",
        "repair_order": None,
    })


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def repair_order_edit(request, pk):
    ro = get_object_or_404(RepairOrder, pk=pk)
    if is_final_repair_order_status(ro.status):
        messages.error(
            request,
            f"Repair order {ro.repair_order_number} is final and cannot be edited.",
        )
        return redirect("repair_orders:detail", pk=ro.pk)

    if request.method == "POST":
        form = RepairOrderEditForm(request.POST, instance=ro)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.updated_by = request.user
            updated.save()
            messages.success(request, f"Repair order {ro.repair_order_number} updated.")
            return redirect("repair_orders:detail", pk=ro.pk)
    else:
        form = RepairOrderEditForm(instance=ro)
    return render(request, "repair_orders/repair_order_form.html", {
        "form": form,
        "mode": "edit",
        "title": f"Edit Repair Order {ro.repair_order_number}",
        "submit_label": "Save Changes",
        "repair_order": ro,
    })
