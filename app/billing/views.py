from urllib.parse import urlencode

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.authorization import (
    PERM_BILLING_MANAGE,
    PERM_BILLING_RECORD_PAYMENT,
    PERM_BILLING_VIEW,
    app_permission_required,
)
from accounts.policies import (
    can_manage_invoice,
    can_manage_invoice_for_repair_order,
    can_manage_invoice_line_items,
    can_record_payment,
    can_view_invoice,
    require_policy,
)
from core.document_numbers import generate_invoice_number
from core.pagination import paginate_queryset, pagination_querystring
from repair_orders.business_rules import is_final_repair_order_status
from repair_orders.models import RepairOrder

from .forms import InvoiceCreateForm, InvoiceEditForm, InvoiceLineItemForm, PaymentForm
from .models import Invoice, InvoiceLineItem
from .services import (
    InvoiceIssueBlocked,
    InvoiceLineItemMutationBlocked,
    InvoiceVoidBlocked,
    PaymentRecordingBlocked,
    create_invoice_line_item,
    edit_invoice_line_item,
    ensure_invoice_line_items_mutable,
    ensure_payment_recordable,
    issue_invoice,
    record_payment,
    void_invoice,
)


_VALID_INVOICE_STATUSES = set(Invoice.Status.values)


def _repair_order_is_final(ro):
    return is_final_repair_order_status(ro.status)


def _final_repair_order_message(ro):
    return f"Repair order {ro.repair_order_number} is final and billing cannot be changed."


def _final_invoice_message(invoice):
    return (
        f"Invoice {invoice.invoice_number} belongs to a final repair order "
        "and cannot be changed."
    )


def _invoice_status_filters(q, status_filter):
    base_params = {}
    if q:
        base_params["q"] = q

    filters = [
        {
            "label": "All",
            "value": "",
            "href": f"?{urlencode(base_params)}" if base_params else "?",
            "active": not status_filter,
        }
    ]

    for value, label in Invoice.Status.choices:
        params = {"status": value, **base_params}
        filters.append(
            {
                "label": label,
                "value": value,
                "href": f"?{urlencode(params)}",
                "active": status_filter == value,
            }
        )
    return filters


@app_permission_required(PERM_BILLING_VIEW)
def invoice_list(request):
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    if status_filter not in _VALID_INVOICE_STATUSES:
        status_filter = ""

    invoices = (
        Invoice.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
        )
        .order_by("-updated_at", "-id")
    )

    if status_filter:
        invoices = invoices.filter(status=status_filter)

    if q:
        invoices = invoices.filter(
            Q(invoice_number__icontains=q)
            | Q(repair_order__repair_order_number__icontains=q)
            | Q(repair_order__customer__first_name__icontains=q)
            | Q(repair_order__customer__last_name__icontains=q)
            | Q(repair_order__customer__business_name__icontains=q)
            | Q(repair_order__vehicle__vin__icontains=q)
            | Q(repair_order__vehicle__make__icontains=q)
            | Q(repair_order__vehicle__model__icontains=q)
            | Q(repair_order__vehicle__license_plate__icontains=q)
        )

    if q:
        empty_state_message = "No invoices match this search."
    elif status_filter:
        empty_state_message = "No invoices match this filter."
    else:
        empty_state_message = "No invoices found."

    clear_search_href = "?"
    if status_filter:
        clear_search_href = f"?status={status_filter}"

    page_obj = paginate_queryset(request, invoices)
    return render(
        request,
        "billing/invoice_list.html",
        {
            "invoices": page_obj.object_list,
            "page_obj": page_obj,
            "pagination_query": pagination_querystring(request),
            "q": q,
            "status_filter": status_filter,
            "status_choices": Invoice.Status.choices,
            "status_filters": _invoice_status_filters(q, status_filter),
            "clear_search_href": clear_search_href,
            "empty_state_message": empty_state_message,
        },
    )


@app_permission_required(PERM_BILLING_VIEW)
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
            "source_estimate",
        ),
        pk=pk,
    )
    ro = invoice.repair_order
    require_policy(can_view_invoice(request.user, invoice))
    line_items = list(invoice.line_items.all())
    payments = list(
        invoice.payments.select_related("received_by").order_by("-payment_date", "-created_at")
    )
    return render(request, "billing/invoice_detail.html", {
        "invoice": invoice,
        "is_final_repair_order": _repair_order_is_final(ro),
        "ro": ro,
        "line_items": line_items,
        "payments": payments,
        "can_manage_invoice": can_manage_invoice(request.user, invoice),
        "can_manage_invoice_line_items": can_manage_invoice_line_items(request.user, invoice),
        "can_record_payment": can_record_payment(request.user, invoice),
    })


@app_permission_required(PERM_BILLING_MANAGE)
def invoice_create_for_repair_order(request, repair_order_pk):
    ro = get_object_or_404(
        RepairOrder.objects.select_related("customer", "vehicle"),
        pk=repair_order_pk,
    )
    require_policy(can_manage_invoice_for_repair_order(request.user, ro))

    if _repair_order_is_final(ro):
        messages.error(request, _final_repair_order_message(ro))
        return redirect("repair_orders:detail", pk=ro.pk)

    # Prevent duplicate invoice — one invoice per repair order.
    try:
        existing = ro.invoice
        messages.info(
            request,
            f"Repair order {ro.repair_order_number} already has "
            f"invoice {existing.invoice_number}.",
        )
        return redirect("repair_orders:detail", pk=ro.pk)
    except RepairOrder.invoice.RelatedObjectDoesNotExist:
        pass

    if request.method == "POST":
        form = InvoiceCreateForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.invoice_number = generate_invoice_number()
            invoice.repair_order = ro
            invoice.created_by = request.user
            invoice.updated_by = request.user
            invoice.save()
            messages.success(request, f"Invoice {invoice.invoice_number} created.")
            return redirect("repair_orders:detail", pk=ro.pk)
    else:
        form = InvoiceCreateForm()

    return render(request, "billing/invoice_form.html", {
        "form": form,
        "ro": ro,
        "invoice": None,
        "mode": "create",
        "title": f"New Invoice for RO {ro.repair_order_number}",
        "submit_label": "Create Invoice",
    })


@app_permission_required(PERM_BILLING_MANAGE)
def invoice_edit(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
        ),
        pk=pk,
    )
    ro = invoice.repair_order
    require_policy(can_manage_invoice(request.user, invoice))

    if _repair_order_is_final(ro):
        messages.error(request, _final_invoice_message(invoice))
        return redirect("billing:invoice_detail", pk=invoice.pk)

    if invoice.status == Invoice.Status.VOID:
        messages.error(request, f"Invoice {invoice.invoice_number} is void and cannot be edited.")
        return redirect("billing:invoice_detail", pk=invoice.pk)

    if request.method == "POST":
        form = InvoiceEditForm(request.POST, instance=invoice)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.updated_by = request.user
            updated.save()
            messages.success(request, f"Invoice {invoice.invoice_number} updated.")
            return redirect("repair_orders:detail", pk=ro.pk)
    else:
        form = InvoiceEditForm(instance=invoice)

    return render(request, "billing/invoice_form.html", {
        "form": form,
        "ro": ro,
        "invoice": invoice,
        "mode": "edit",
        "title": f"Edit Invoice {invoice.invoice_number}",
        "submit_label": "Save Changes",
    })


@app_permission_required(PERM_BILLING_MANAGE)
def invoice_issue(request, pk):
    if request.method != "POST":
        return redirect("billing:invoice_detail", pk=pk)

    invoice = get_object_or_404(Invoice.objects.select_related("repair_order"), pk=pk)
    ro = invoice.repair_order
    require_policy(can_manage_invoice(request.user, invoice))

    try:
        issue_invoice(invoice, actor=request.user)
    except InvoiceIssueBlocked as error:
        if _repair_order_is_final(ro):
            messages.error(request, str(error))
            return redirect("billing:invoice_detail", pk=invoice.pk)
        if invoice.status != Invoice.Status.DRAFT:
            messages.info(request, str(error))
            return redirect("repair_orders:detail", pk=ro.pk)
        messages.error(request, str(error))
        return redirect("billing:invoice_detail", pk=invoice.pk)

    messages.success(request, f"Invoice {invoice.invoice_number} issued.")
    return redirect("repair_orders:detail", pk=ro.pk)


@app_permission_required(PERM_BILLING_MANAGE)
def invoice_void(request, pk):
    if request.method != "POST":
        return redirect("billing:invoice_detail", pk=pk)

    invoice = get_object_or_404(Invoice.objects.select_related("repair_order"), pk=pk)
    ro = invoice.repair_order
    require_policy(can_manage_invoice(request.user, invoice))

    try:
        void_invoice(invoice, actor=request.user)
    except InvoiceVoidBlocked as error:
        if _repair_order_is_final(ro):
            messages.error(request, str(error))
            return redirect("billing:invoice_detail", pk=invoice.pk)
        if invoice.status == Invoice.Status.VOID:
            messages.info(request, str(error))
            return redirect("repair_orders:detail", pk=ro.pk)
        messages.error(request, str(error))
        return redirect("billing:invoice_detail", pk=invoice.pk)

    messages.success(request, f"Invoice {invoice.invoice_number} voided.")
    return redirect("repair_orders:detail", pk=ro.pk)


@app_permission_required(PERM_BILLING_RECORD_PAYMENT)
def payment_create(request, invoice_pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
        ),
        pk=invoice_pk,
    )
    ro = invoice.repair_order
    require_policy(can_record_payment(request.user, invoice))

    try:
        ensure_payment_recordable(invoice)
    except PaymentRecordingBlocked as error:
        messages.error(request, str(error))
        return redirect("repair_orders:detail", pk=ro.pk)

    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                payment = record_payment(invoice, form.cleaned_data, actor=request.user)
            except PaymentRecordingBlocked as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, f"Payment of ${payment.amount} recorded.")
                return redirect("repair_orders:detail", pk=ro.pk)
    else:
        form = PaymentForm()

    return render(request, "billing/payment_form.html", {
        "form": form,
        "invoice": invoice,
        "ro": ro,
        "title": f"Record Payment for Invoice {invoice.invoice_number}",
        "submit_label": "Record Payment",
    })


@app_permission_required(PERM_BILLING_MANAGE)
def line_item_create(request, invoice_pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
        ),
        pk=invoice_pk,
    )
    ro = invoice.repair_order
    require_policy(can_manage_invoice_line_items(request.user, invoice))

    try:
        ensure_invoice_line_items_mutable(invoice)
    except InvoiceLineItemMutationBlocked as error:
        messages.error(request, str(error))
        return redirect("billing:invoice_detail", pk=invoice.pk)

    if request.method == "POST":
        form = InvoiceLineItemForm(request.POST, invoice=invoice)
        if form.is_valid():
            try:
                create_invoice_line_item(
                    invoice,
                    form.cleaned_data,
                    actor=request.user,
                )
            except InvoiceLineItemMutationBlocked as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, "Invoice line item added.")
                return redirect("repair_orders:detail", pk=ro.pk)
    else:
        form = InvoiceLineItemForm(invoice=invoice)

    return render(request, "billing/line_item_form.html", {
        "form": form,
        "invoice": invoice,
        "line_item": None,
        "ro": ro,
        "mode": "create",
        "title": f"Add Line Item to Invoice {invoice.invoice_number}",
        "submit_label": "Add Line Item",
    })


@app_permission_required(PERM_BILLING_MANAGE)
def line_item_edit(request, pk):
    line_item = get_object_or_404(
        InvoiceLineItem.objects.select_related(
            "invoice",
            "invoice__repair_order",
            "invoice__repair_order__customer",
            "invoice__repair_order__vehicle",
        ),
        pk=pk,
    )
    invoice = line_item.invoice
    ro = invoice.repair_order
    require_policy(can_manage_invoice_line_items(request.user, invoice))

    try:
        ensure_invoice_line_items_mutable(invoice)
    except InvoiceLineItemMutationBlocked as error:
        messages.error(request, str(error))
        return redirect("billing:invoice_detail", pk=invoice.pk)

    if request.method == "POST":
        form = InvoiceLineItemForm(request.POST, instance=line_item)
        if form.is_valid():
            try:
                edit_invoice_line_item(line_item, form.cleaned_data, actor=request.user)
            except InvoiceLineItemMutationBlocked as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, "Invoice line item updated.")
                return redirect("repair_orders:detail", pk=ro.pk)
    else:
        form = InvoiceLineItemForm(instance=line_item)

    return render(request, "billing/line_item_form.html", {
        "form": form,
        "invoice": invoice,
        "line_item": line_item,
        "ro": ro,
        "mode": "edit",
        "title": f"Edit Line Item for Invoice {invoice.invoice_number}",
        "submit_label": "Save Changes",
    })
