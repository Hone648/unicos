from accounts.authorization import (
    PERM_CUSTOMERS_VIEW,
    PERM_REPAIR_ORDERS_CHANGE_STATUS,
    PERM_REPAIR_ORDERS_MANAGE,
    PERM_REPAIR_ORDERS_VIEW,
    app_permission_required,
    user_has_app_permission,
)
from accounts.policies import (
    can_add_communication_for_repair_order,
    can_change_repair_order_status,
    can_edit_repair_order,
    can_manage_estimate_for_repair_order,
    can_manage_invoice,
    can_manage_invoice_for_repair_order,
    can_manage_invoice_line_items,
    can_record_payment,
    can_upload_attachment_for_repair_order,
    can_view_invoice,
    can_view_invoice_for_repair_order,
    filter_repair_orders_for_user,
    is_owner_admin_or_manager,
    require_policy,
)
from accounts.policies import can_view_repair_order as policy_can_view_repair_order
from billing.services import PaymentRecordingBlocked, ensure_payment_recordable
from core.document_numbers import generate_repair_order_number
from core.pagination import paginate_queryset, pagination_querystring
from customers.models import Customer
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from vehicles.models import Vehicle

from .business_rules import closure_blocked_by_invoice, is_final_repair_order_status
from .forms import RepairOrderCreateForm, RepairOrderEditForm
from .models import RepairOrder
from .services import (
    RepairOrderStatusTransitionBlocked,
    RepairOrderTransitionInvalid,
    transition_repair_order_status,
)
from .status_continuation import (
    sign_status_continuation,
    status_controls_url,
    validated_continuation,
)
from .transition_policy import (
    CANCELABLE_STATUSES,
    REOPEN_TARGETS,
    can_use_exceptions,
    routine_choices,
)

# Status values that count as "closed" for default list filtering
_CLOSED_STATUSES = {RepairOrder.Status.CLOSED, RepairOrder.Status.CANCELED}

# All valid status values for quick lookup
_VALID_STATUSES = set(RepairOrder.Status.values)


def _posted_customer_id(request):
    return request.POST.get("customer") or None


def _status_payment_url(invoice, token):
    try:
        ensure_payment_recordable(invoice)
    except PaymentRecordingBlocked:
        return ""
    return reverse(
        "billing:payment_create",
        kwargs={"invoice_pk": invoice.pk},
        query={"status_continuation": token},
    )


def _repair_order_detail_context(ro, user, *, status_continuation=None):
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
        ro.estimates.select_related("parent_estimate", "created_by", "updated_by").order_by(
            "-updated_at", "-id"
        )
    )
    attachments = list(ro.attachments.select_related("uploaded_by").order_by("-created_at", "-id"))
    communications = list(
        ro.communications.select_related("created_by").order_by("-occurred_at", "-id")[:10]
    )
    can_upload_attachments = can_upload_attachment_for_repair_order(user, ro)
    can_delete_attachments = is_owner_admin_or_manager(user)
    may_change_status = can_change_repair_order_status(user, ro)
    may_view_invoice = (
        can_view_invoice(user, invoice) if invoice else can_view_invoice_for_repair_order(user, ro)
    )
    may_record_payment = bool(invoice and can_record_payment(user, invoice))
    choices = routine_choices(ro.status)
    selected_status = ""
    pending_action = "routine"
    blocking_invoice = None
    status_payment_url = ""
    payment_recorded = False
    status_continuation_active = False
    data = validated_continuation(invoice, status_continuation, user) if may_change_status else None
    if data:
        status_continuation_active = True
        pending_action = data["action"]
        selected_status = data["status"] if pending_action == "routine" else ""
        payment_recorded = data["paid"]
        blocking_invoice = closure_blocked_by_invoice(ro, data["status"])
        if blocking_invoice and may_view_invoice and may_record_payment:
            status_payment_url = _status_payment_url(blocking_invoice, status_continuation)

    may_create_estimate = can_manage_estimate_for_repair_order(user, ro)
    show_intake_estimate_action = (
        ro.status == RepairOrder.Status.INTAKE
        and not estimates
        and may_create_estimate
        and not status_continuation_active
    )
    displayed_closed_at = ro.closed_at if ro.status == RepairOrder.Status.CLOSED else None
    if ro.status == RepairOrder.Status.CLOSED and not displayed_closed_at:
        displayed_closed_at = (
            history.filter(new_status=RepairOrder.Status.CLOSED)
            .values_list("changed_at", flat=True)
            .first()
        )

    return {
        "ro": ro,
        "displayed_closed_at": displayed_closed_at,
        "show_intake_estimate_action": show_intake_estimate_action,
        "history": history,
        "invoice": invoice,
        "is_final_repair_order": is_final_repair_order_status(ro.status),
        "line_items": line_items,
        "payments": payments,
        "estimates": estimates,
        "status_choices": choices,
        "pending_action": pending_action,
        "invalid_continuation": bool(status_continuation and not data),
        "can_cancel_repair_order": can_use_exceptions(user, ro)
        and ro.status in CANCELABLE_STATUSES,
        "can_reopen_repair_order": can_use_exceptions(user, ro) and ro.status in REOPEN_TARGETS,
        "reopen_status_label": dict(RepairOrder.Status.choices).get(REOPEN_TARGETS.get(ro.status)),
        "selected_status": selected_status,
        "selected_status_label": dict(RepairOrder.Status.choices).get(
            data["status"] if data else selected_status
        ),
        "blocking_invoice": blocking_invoice,
        "status_payment_url": status_payment_url,
        "payment_recorded": payment_recorded and may_view_invoice,
        "payment_paid_in_full": payment_recorded and may_view_invoice and invoice.is_paid,
        "can_edit_repair_order": can_edit_repair_order(user, ro),
        "can_change_repair_order_status": may_change_status,
        "can_create_estimate": may_create_estimate,
        "can_view_invoice": may_view_invoice,
        "can_manage_invoice": bool(invoice and can_manage_invoice(user, invoice)),
        "can_create_invoice": can_manage_invoice_for_repair_order(user, ro),
        "can_record_payment": may_record_payment,
        "can_manage_invoice_line_items": bool(
            invoice and can_manage_invoice_line_items(user, invoice)
        ),
        "attachments": attachments,
        "can_upload_attachments": can_upload_attachments,
        "can_delete_attachments": can_delete_attachments,
        "communications": communications,
        "can_add_communication": can_add_communication_for_repair_order(user, ro),
    }


@app_permission_required(PERM_REPAIR_ORDERS_VIEW)
def repair_order_list(request):
    qs = RepairOrder.objects.select_related("customer", "vehicle", "assigned_to").order_by(
        "-opened_at", "-id"
    )
    qs = filter_repair_orders_for_user(request.user, qs)

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
    require_policy(policy_can_view_repair_order(request.user, ro))
    return render(
        request,
        "repair_orders/repair_order_detail.html",
        _repair_order_detail_context(
            ro, request.user, status_continuation=request.GET.get("status_continuation")
        ),
    )


@app_permission_required(PERM_REPAIR_ORDERS_CHANGE_STATUS)
def repair_order_status_update(request, pk):
    if request.method != "POST":
        return redirect("repair_orders:detail", pk=pk)

    is_htmx = request.headers.get("HX-Request") == "true"

    ro = get_object_or_404(RepairOrder, pk=pk)
    require_policy(can_change_repair_order_status(request.user, ro))
    action = request.POST.get("transition_action", "routine")
    new_status = request.POST.get("new_status", "").strip()
    if action == "cancel":
        new_status = RepairOrder.Status.CANCELED
    elif action == "reopen":
        new_status = REOPEN_TARGETS.get(ro.status, "")
    note = request.POST.get("note", "").strip() or "Status changed from repair order workspace."
    reason = request.POST.get("reason", "").strip()
    expected_status = request.POST.get("expected_status", "")
    original_status = ro.status
    error = ""
    try:
        if expected_status not in _VALID_STATUSES:
            raise RepairOrderTransitionInvalid(
                "Reload this page to supply the current status, then choose an available action."
            )
        if action == "routine" and not new_status:
            raise RepairOrderTransitionInvalid(
                "Choose a next status before selecting Update Status."
            )
        if action == "routine" and new_status not in _VALID_STATUSES:
            raise RepairOrderTransitionInvalid(
                f"'{new_status}' is not a valid repair order status."
            )
        transition_repair_order_status(
            ro,
            new_status,
            changed_by=request.user,
            note=note,
            action=action,
            reason=reason,
            expected_status=expected_status,
        )
    except RepairOrderStatusTransitionBlocked as exc:
        token = sign_status_continuation(
            exc.invoice, new_status, source_status=ro.status, action=action
        )
        if not is_htmx:
            return redirect(status_controls_url(pk, token))
        return render(
            request,
            "repair_orders/partials/_status_update_response.html",
            _repair_order_detail_context(ro, request.user, status_continuation=token),
        )
    except RepairOrderTransitionInvalid as exc:
        error = str(exc)
        messages.error(request, error)
    else:
        if original_status == ro.status:
            messages.info(request, "Status is already set to that value — no change made.")
        else:
            messages.success(request, f'Status updated to "{ro.get_status_display()}".')
    if not is_htmx:
        return redirect("repair_orders:detail", pk=pk)
    if (
        not error
        and original_status != ro.status
        and (is_final_repair_order_status(ro.status) or action == "reopen")
    ):
        return HttpResponse(
            headers={"HX-Redirect": reverse("repair_orders:detail", kwargs={"pk": pk})}
        )
    context = _repair_order_detail_context(ro, request.user)
    context["transition_error"] = error
    return render(request, "repair_orders/partials/_status_update_response.html", context)


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def repair_order_create(request, customer_pk=None, vehicle_pk=None):
    intake_customer = None
    intake_vehicle = None
    cancel_url = reverse("repair_orders:list")
    back_label = "Repair Orders"
    if customer_pk is not None or vehicle_pk is not None:
        require_policy(user_has_app_permission(request.user, PERM_CUSTOMERS_VIEW))
        if vehicle_pk is not None:
            intake_vehicle = get_object_or_404(
                Vehicle.objects.select_related("customer"), pk=vehicle_pk, is_active=True
            )
            intake_customer = intake_vehicle.customer
            cancel_url = reverse("vehicles:detail", kwargs={"pk": intake_vehicle.pk})
            back_label = str(intake_vehicle)
        else:
            intake_customer = get_object_or_404(Customer, pk=customer_pk)
            cancel_url = reverse("customers:detail", kwargs={"pk": intake_customer.pk})
            back_label = intake_customer.display_name

    is_post = request.method == "POST"
    form = RepairOrderCreateForm(
        request.POST if is_post else None,
        intake_customer=intake_customer,
        intake_vehicle=intake_vehicle,
        enable_vehicle_htmx=True,
    )
    if is_post and form.is_valid():
        ro = form.save(commit=False)
        ro.repair_order_number = generate_repair_order_number()
        ro.created_by = request.user
        ro.updated_by = request.user
        ro.save()
        messages.success(request, f"Repair order {ro.repair_order_number} created.")
        return redirect("repair_orders:detail", pk=ro.pk)
    return render(
        request,
        "repair_orders/repair_order_form.html",
        {
            "form": form,
            "mode": "create",
            "title": "New Repair Order",
            "submit_label": "Create Repair Order",
            "repair_order": None,
            "intake_customer": intake_customer,
            "cancel_url": cancel_url,
            "back_label": back_label,
        },
    )


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def repair_order_vehicle_field(request):
    form = RepairOrderCreateForm(customer_id=request.GET.get("customer") or None)
    return render(
        request,
        "repair_orders/partials/_vehicle_field.html",
        {
            "form": form,
        },
    )


@app_permission_required(PERM_REPAIR_ORDERS_MANAGE)
def repair_order_edit(request, pk):
    ro = get_object_or_404(RepairOrder, pk=pk)
    require_policy(can_edit_repair_order(request.user, ro))
    if is_final_repair_order_status(ro.status):
        messages.error(
            request,
            f"Repair order {ro.repair_order_number} is final and cannot be edited.",
        )
        return redirect("repair_orders:detail", pk=ro.pk)

    if request.method == "POST":
        form = RepairOrderEditForm(
            request.POST,
            instance=ro,
            customer_id=_posted_customer_id(request),
        )
        if form.is_valid():
            updated = form.save(commit=False)
            updated.updated_by = request.user
            updated.save()
            messages.success(request, f"Repair order {ro.repair_order_number} updated.")
            return redirect("repair_orders:detail", pk=ro.pk)
    else:
        form = RepairOrderEditForm(instance=ro)
    return render(
        request,
        "repair_orders/repair_order_form.html",
        {
            "form": form,
            "mode": "edit",
            "title": f"Edit Repair Order {ro.repair_order_number}",
            "submit_label": "Save Changes",
            "repair_order": ro,
        },
    )
