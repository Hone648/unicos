from decimal import Decimal

from accounts.authorization import (
    PERM_DASHBOARD_VIEW,
    PERM_REPORTS_VIEW,
    app_permission_required,
)
from billing.models import Invoice
from django.db import connections
from django.db.models import DecimalField, ExpressionWrapper, F, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import render
from estimates.models import Estimate
from repair_orders.business_rules import (
    FINAL_REPAIR_ORDER_STATUSES,
    is_final_repair_order_status,
)
from repair_orders.models import RepairOrder


def _dashboard_context():
    active_repair_orders = RepairOrder.objects.exclude(status__in=FINAL_REPAIR_ORDER_STATUSES)
    ready_for_pickup = (
        active_repair_orders.filter(status=RepairOrder.Status.READY_FOR_PICKUP)
        .select_related("customer", "vehicle")
        .order_by("-updated_at", "-id")
    )

    invoices = (
        Invoice.objects.exclude(status=Invoice.Status.VOID)
        .select_related("repair_order", "repair_order__customer", "repair_order__vehicle")
        .order_by("-updated_at", "-id")
    )
    unpaid_invoices = [invoice for invoice in invoices if invoice.balance_due > 0]
    blocked_from_closure_invoices = [
        invoice
        for invoice in unpaid_invoices
        if not is_final_repair_order_status(invoice.repair_order.status)
    ]

    recent_repair_orders = RepairOrder.objects.select_related("customer", "vehicle").order_by(
        "-updated_at", "-id"
    )[:5]

    return {
        "active_repair_order_count": active_repair_orders.count(),
        "repair_orders_status_ready_for_pickup": RepairOrder.Status.READY_FOR_PICKUP,
        "ready_for_pickup_count": ready_for_pickup.count(),
        "ready_for_pickup_repair_orders": list(ready_for_pickup[:5]),
        "unpaid_invoice_count": len(unpaid_invoices),
        "unpaid_invoice_total": sum(
            (invoice.balance_due for invoice in unpaid_invoices),
            start=Decimal("0.00"),
        ),
        "unpaid_invoices": unpaid_invoices[:5],
        "blocked_from_closure_count": len(blocked_from_closure_invoices),
        "blocked_from_closure_invoices": blocked_from_closure_invoices[:5],
        "recent_repair_orders": list(recent_repair_orders),
    }


@app_permission_required(PERM_DASHBOARD_VIEW)
def dashboard(request):
    return render(request, "core/dashboard.html", _dashboard_context())


def _invoice_balance_expression():
    paid_amount = Coalesce(
        Sum("payments__amount"),
        Value(Decimal("0.00")),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
    return ExpressionWrapper(
        F("subtotal") + F("tax_amount") - paid_amount,
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )


def _reports_context():
    active_repair_orders = RepairOrder.objects.exclude(status__in=FINAL_REPAIR_ORDER_STATUSES)
    final_repair_orders = RepairOrder.objects.filter(status__in=FINAL_REPAIR_ORDER_STATUSES)

    annotated_invoices = Invoice.objects.annotate(balance_due_amount=_invoice_balance_expression())
    non_void_invoices = annotated_invoices.exclude(status=Invoice.Status.VOID)
    unpaid_invoices = non_void_invoices.filter(balance_due_amount__gt=Decimal("0.00"))
    top_unpaid_invoices = unpaid_invoices.select_related(
        "repair_order",
        "repair_order__customer",
        "repair_order__vehicle",
    ).order_by("-balance_due_amount", "-updated_at", "-id")[:10]
    total_balance_due = sum(
        unpaid_invoices.values_list("balance_due_amount", flat=True),
        Decimal("0.00"),
    )

    approved_estimates = Estimate.objects.filter(status=Estimate.Status.APPROVED)
    approved_with_capture = (
        approved_estimates.exclude(
            approval_source="",
        )
        .exclude(
            approval_contact_name="",
        )
        .filter(
            approved_at__isnull=False,
        )
    )
    approved_missing_capture = approved_estimates.exclude(pk__in=approved_with_capture.values("pk"))
    approved_converted = approved_estimates.filter(converted_invoices__isnull=False)
    approved_not_converted = approved_estimates.filter(converted_invoices__isnull=True)
    estimates_needing_attention = (
        Estimate.objects.filter(
            status__in=[Estimate.Status.SUBMITTED, Estimate.Status.APPROVED],
        )
        .select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
        )
        .prefetch_related("converted_invoices")
        .order_by("-updated_at", "-id")
    )
    estimate_attention_rows = []
    for estimate in estimates_needing_attention:
        reason = _estimate_attention_reason(estimate)
        if reason:
            estimate_attention_rows.append(
                {
                    "estimate": estimate,
                    "reason": reason,
                }
            )
        if len(estimate_attention_rows) == 10:
            break

    return {
        "active_repair_order_count": active_repair_orders.count(),
        "ready_for_pickup_count": active_repair_orders.filter(
            status=RepairOrder.Status.READY_FOR_PICKUP
        ).count(),
        "final_repair_order_count": final_repair_orders.count(),
        "unassigned_active_repair_order_count": active_repair_orders.filter(
            assigned_to__isnull=True
        ).count(),
        "ready_for_pickup_repair_orders": list(
            active_repair_orders.filter(status=RepairOrder.Status.READY_FOR_PICKUP)
            .select_related("customer", "vehicle", "assigned_to")
            .order_by("promised_date", "-updated_at", "-id")[:10]
        ),
        "non_void_invoice_count": non_void_invoices.count(),
        "unpaid_invoice_count": unpaid_invoices.count(),
        "total_balance_due": total_balance_due,
        "draft_invoice_count": annotated_invoices.filter(status=Invoice.Status.DRAFT).count(),
        "issued_or_partially_paid_invoice_count": annotated_invoices.filter(
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PARTIALLY_PAID]
        ).count(),
        "paid_invoice_count": annotated_invoices.filter(status=Invoice.Status.PAID).count(),
        "void_invoice_count": annotated_invoices.filter(status=Invoice.Status.VOID).count(),
        "top_unpaid_invoices": list(top_unpaid_invoices),
        "draft_estimate_count": Estimate.objects.filter(status=Estimate.Status.DRAFT).count(),
        "submitted_estimate_count": Estimate.objects.filter(
            status=Estimate.Status.SUBMITTED
        ).count(),
        "approved_estimate_count": approved_estimates.count(),
        "approved_with_capture_count": approved_with_capture.count(),
        "approved_missing_capture_count": approved_missing_capture.count(),
        "approved_converted_count": approved_converted.count(),
        "approved_not_converted_count": approved_not_converted.count(),
        "estimates_needing_attention": estimate_attention_rows,
    }


def _estimate_attention_reason(estimate):
    if estimate.status == Estimate.Status.SUBMITTED:
        return "Awaiting decision"
    if estimate.status == Estimate.Status.APPROVED and not estimate.has_approval_capture:
        return "Missing approval capture"
    if estimate.status == Estimate.Status.APPROVED and not estimate.converted_invoices.exists():
        return "Not converted to invoice"
    return ""


@app_permission_required(PERM_REPORTS_VIEW)
def reports(request):
    return render(request, "core/reports.html", _reports_context())


def healthz(request):
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:
        return JsonResponse(
            {
                "status": "error",
                "database": "error",
                "error": str(exc),
            },
            status=503,
        )

    return JsonResponse(
        {
            "status": "ok",
            "database": "ok",
        }
    )
