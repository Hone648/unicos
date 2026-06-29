from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import connections
from django.http import JsonResponse
from django.shortcuts import render

from billing.models import Invoice
from repair_orders.business_rules import (
    FINAL_REPAIR_ORDER_STATUSES,
    is_final_repair_order_status,
)
from repair_orders.models import RepairOrder


def _dashboard_context():
    active_repair_orders = RepairOrder.objects.exclude(
        status__in=FINAL_REPAIR_ORDER_STATUSES
    )
    ready_for_pickup = active_repair_orders.filter(
        status=RepairOrder.Status.READY_FOR_PICKUP
    ).select_related("customer", "vehicle").order_by("-updated_at", "-id")

    invoices = (
        Invoice.objects.exclude(status=Invoice.Status.VOID)
        .select_related("repair_order", "repair_order__customer", "repair_order__vehicle")
        .order_by("-updated_at", "-id")
    )
    unpaid_invoices = [
        invoice for invoice in invoices if invoice.balance_due > 0
    ]
    blocked_from_closure_invoices = [
        invoice
        for invoice in unpaid_invoices
        if not is_final_repair_order_status(invoice.repair_order.status)
    ]

    recent_repair_orders = RepairOrder.objects.select_related(
        "customer", "vehicle"
    ).order_by("-updated_at", "-id")[:5]

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


@login_required
def dashboard(request):
    return render(request, "core/dashboard.html", _dashboard_context())


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
