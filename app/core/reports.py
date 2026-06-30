import csv
from dataclasses import dataclass
from decimal import Decimal

from billing.models import Invoice
from django.db.models import DecimalField, ExpressionWrapper, F, QuerySet, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponse, QueryDict
from estimates.models import Estimate
from repair_orders.business_rules import FINAL_REPAIR_ORDER_STATUSES
from repair_orders.models import RepairOrder

from .forms import ALL_STATUSES

REPORT_EXPORT_REPAIR_ORDERS = "repair_orders"
REPORT_EXPORT_INVOICES = "invoices"
REPORT_EXPORT_ESTIMATES = "estimates"
REPORT_EXPORTS = {
    REPORT_EXPORT_REPAIR_ORDERS,
    REPORT_EXPORT_INVOICES,
    REPORT_EXPORT_ESTIMATES,
}
REPORT_TABLE_LIMIT = 10
UNSAFE_CSV_PREFIXES = ("=", "+", "-", "@")


@dataclass(frozen=True)
class ReportQuerysets:
    repair_orders: QuerySet[RepairOrder]
    invoices: QuerySet[Invoice]
    estimates: QuerySet[Estimate]


def build_reports_context(filter_form, query_params=None, *, table_limit=REPORT_TABLE_LIMIT):
    filters = active_report_filters(filter_form)
    querysets = build_report_querysets(filters)
    repair_orders = querysets.repair_orders
    active_repair_orders = repair_orders.exclude(status__in=FINAL_REPAIR_ORDER_STATUSES)
    final_repair_orders = repair_orders.filter(status__in=FINAL_REPAIR_ORDER_STATUSES)

    invoices = querysets.invoices
    non_void_invoices = invoices.exclude(status=Invoice.Status.VOID)
    unpaid_invoices = non_void_invoices.filter(balance_due_amount__gt=Decimal("0.00"))
    top_unpaid_invoices = unpaid_invoices.order_by("-balance_due_amount", "-updated_at", "-id")
    total_balance_due = sum(
        unpaid_invoices.values_list("balance_due_amount", flat=True),
        Decimal("0.00"),
    )

    estimates = querysets.estimates
    approved_estimates = estimates.filter(status=Estimate.Status.APPROVED)
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

    return {
        "filter_form": filter_form,
        "active_filters": filters,
        "csv_export_querystrings": csv_export_querystrings(query_params or QueryDict()),
        "active_filter_querystring": filter_querystring(query_params or QueryDict()),
        "active_repair_order_count": active_repair_orders.count(),
        "ready_for_pickup_count": active_repair_orders.filter(
            status=RepairOrder.Status.READY_FOR_PICKUP
        ).count(),
        "final_repair_order_count": final_repair_orders.count(),
        "unassigned_active_repair_order_count": active_repair_orders.filter(
            assigned_to__isnull=True
        ).count(),
        "ready_for_pickup_repair_orders": list(
            limit_queryset(
                active_repair_orders.filter(status=RepairOrder.Status.READY_FOR_PICKUP).order_by(
                    "promised_date", "-updated_at", "-id"
                ),
                table_limit,
            )
        ),
        "non_void_invoice_count": non_void_invoices.count(),
        "unpaid_invoice_count": unpaid_invoices.count(),
        "total_balance_due": total_balance_due,
        "draft_invoice_count": invoices.filter(status=Invoice.Status.DRAFT).count(),
        "issued_or_partially_paid_invoice_count": invoices.filter(
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PARTIALLY_PAID]
        ).count(),
        "paid_invoice_count": invoices.filter(status=Invoice.Status.PAID).count(),
        "void_invoice_count": invoices.filter(status=Invoice.Status.VOID).count(),
        "top_unpaid_invoices": list(limit_queryset(top_unpaid_invoices, table_limit)),
        "draft_estimate_count": estimates.filter(status=Estimate.Status.DRAFT).count(),
        "submitted_estimate_count": estimates.filter(status=Estimate.Status.SUBMITTED).count(),
        "approved_estimate_count": approved_estimates.count(),
        "approved_with_capture_count": approved_with_capture.count(),
        "approved_missing_capture_count": approved_missing_capture.count(),
        "approved_converted_count": approved_converted.count(),
        "approved_not_converted_count": approved_not_converted.count(),
        "estimates_needing_attention": estimate_attention_rows(estimates, table_limit),
    }


def active_report_filters(filter_form):
    if filter_form.is_bound and filter_form.is_valid():
        return filter_form.cleaned_data
    return {
        "start_date": None,
        "end_date": None,
        "repair_order_status": ALL_STATUSES,
        "invoice_status": ALL_STATUSES,
        "estimate_status": ALL_STATUSES,
    }


def build_report_querysets(filters):
    repair_orders = RepairOrder.objects.select_related(
        "customer",
        "vehicle",
        "assigned_to",
    )
    repair_orders = apply_date_range(repair_orders, filters, "opened_at")
    if filters["repair_order_status"] != ALL_STATUSES:
        repair_orders = repair_orders.filter(status=filters["repair_order_status"])

    invoices = Invoice.objects.select_related(
        "repair_order",
        "repair_order__customer",
        "repair_order__vehicle",
    ).annotate(balance_due_amount=invoice_balance_expression())
    invoices = apply_date_range(invoices, filters, "created_at")
    if filters["invoice_status"] != ALL_STATUSES:
        invoices = invoices.filter(status=filters["invoice_status"])

    estimates = Estimate.objects.select_related(
        "repair_order",
        "repair_order__customer",
        "repair_order__vehicle",
    ).prefetch_related("converted_invoices")
    estimates = apply_date_range(estimates, filters, "created_at")
    if filters["estimate_status"] != ALL_STATUSES:
        estimates = estimates.filter(status=filters["estimate_status"])

    return ReportQuerysets(
        repair_orders=repair_orders,
        invoices=invoices,
        estimates=estimates,
    )


def invoice_balance_expression():
    paid_amount = Coalesce(
        Sum("payments__amount"),
        Value(Decimal("0.00")),
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )
    return ExpressionWrapper(
        F("subtotal") + F("tax_amount") - paid_amount,
        output_field=DecimalField(max_digits=10, decimal_places=2),
    )


def apply_date_range(queryset, filters, field_name):
    if filters["start_date"]:
        queryset = queryset.filter(**{f"{field_name}__date__gte": filters["start_date"]})
    if filters["end_date"]:
        queryset = queryset.filter(**{f"{field_name}__date__lte": filters["end_date"]})
    return queryset


def limit_queryset(queryset, limit):
    return queryset if limit is None else queryset[:limit]


def estimate_attention_rows(estimates, table_limit):
    rows = []
    estimates_needing_attention = estimates.filter(
        status__in=[Estimate.Status.SUBMITTED, Estimate.Status.APPROVED],
    ).order_by("-updated_at", "-id")
    for estimate in estimates_needing_attention:
        reason = estimate_attention_reason(estimate)
        if reason:
            rows.append(
                {
                    "estimate": estimate,
                    "reason": reason,
                }
            )
        if table_limit is not None and len(rows) == table_limit:
            break
    return rows


def estimate_attention_reason(estimate):
    if estimate.status == Estimate.Status.SUBMITTED:
        return "Awaiting decision"
    if estimate.status == Estimate.Status.APPROVED and not estimate.has_approval_capture:
        return "Missing approval capture"
    if estimate.status == Estimate.Status.APPROVED and not estimate.converted_invoices.exists():
        return "Not converted to invoice"
    return ""


def csv_export_querystrings(query_params):
    return {
        export: querystring_with_export(query_params, export) for export in sorted(REPORT_EXPORTS)
    }


def querystring_with_export(query_params, export):
    query = query_params.copy()
    query["export"] = export
    return query.urlencode()


def filter_querystring(query_params):
    query = query_params.copy()
    query.pop("export", None)
    return query.urlencode()


def report_csv_response(export, filter_form):
    filters = active_report_filters(filter_form)
    if export == REPORT_EXPORT_REPAIR_ORDERS:
        return repair_orders_csv(filters)
    if export == REPORT_EXPORT_INVOICES:
        return invoices_csv(filters)
    return estimates_csv(filters)


def repair_orders_csv(filters):
    repair_orders = build_report_querysets(filters).repair_orders.order_by("-opened_at", "-id")
    rows = (
        [
            ro.repair_order_number,
            ro.get_status_display(),
            ro.customer.display_name,
            str(ro.vehicle),
            ro.assigned_to.get_username() if ro.assigned_to else "",
            ro.opened_at.isoformat() if ro.opened_at else "",
            ro.promised_date.isoformat() if ro.promised_date else "",
            ro.closed_at.isoformat() if ro.closed_at else "",
        ]
        for ro in repair_orders
    )
    return csv_response(
        "repair-orders-report.csv",
        [
            "Repair Order #",
            "Status",
            "Customer",
            "Vehicle",
            "Assigned To",
            "Opened At",
            "Promised Date",
            "Closed At",
        ],
        rows,
    )


def invoices_csv(filters):
    invoices = build_report_querysets(filters).invoices.order_by("-created_at", "-id")
    rows = (
        [
            invoice.invoice_number,
            invoice.get_status_display(),
            invoice.repair_order.repair_order_number,
            invoice.repair_order.customer.display_name,
            invoice.subtotal,
            invoice.tax_amount,
            invoice.total_amount,
            invoice.balance_due_amount,
            invoice.issued_at.isoformat() if invoice.issued_at else "",
            invoice.due_date.isoformat() if invoice.due_date else "",
            invoice.created_at.isoformat() if invoice.created_at else "",
        ]
        for invoice in invoices
    )
    return csv_response(
        "invoices-report.csv",
        [
            "Invoice #",
            "Status",
            "Repair Order #",
            "Customer",
            "Subtotal",
            "Tax",
            "Total",
            "Balance Due",
            "Issued At",
            "Due Date",
            "Created At",
        ],
        rows,
    )


def estimates_csv(filters):
    estimates = build_report_querysets(filters).estimates.order_by("-created_at", "-id")
    rows = (
        [
            estimate.estimate_number,
            estimate.get_status_display(),
            estimate.get_kind_display(),
            estimate.repair_order.repair_order_number,
            estimate.repair_order.customer.display_name,
            estimate.estimated_total,
            estimate.get_approval_source_display() if estimate.approval_source else "",
            estimate.approval_contact_name,
            estimate.approved_at.isoformat() if estimate.approved_at else "",
            estimate.created_at.isoformat() if estimate.created_at else "",
        ]
        for estimate in estimates
    )
    return csv_response(
        "estimates-report.csv",
        [
            "Estimate #",
            "Status",
            "Kind",
            "Repair Order #",
            "Customer",
            "Estimated Total",
            "Approval Source",
            "Approval Contact",
            "Approved At",
            "Created At",
        ],
        rows,
    )


def csv_response(filename, headers, rows):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([safe_csv_value(value) for value in row])
    return response


def safe_csv_value(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(UNSAFE_CSV_PREFIXES):
        return f"'{text}"
    return text
