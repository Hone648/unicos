from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.document_numbers import generate_invoice_number
from repair_orders.models import RepairOrder

from .forms import InvoiceCreateForm, InvoiceEditForm, InvoiceLineItemForm, PaymentForm
from .models import Invoice, InvoiceLineItem, Payment


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            "repair_order",
            "repair_order__customer",
            "repair_order__vehicle",
        ),
        pk=pk,
    )
    ro = invoice.repair_order
    line_items = list(invoice.line_items.all())
    payments = list(
        invoice.payments.select_related("received_by").order_by("-payment_date", "-created_at")
    )
    return render(request, "billing/invoice_detail.html", {
        "invoice": invoice,
        "ro": ro,
        "line_items": line_items,
        "payments": payments,
    })


@login_required
def invoice_create_for_repair_order(request, repair_order_pk):
    ro = get_object_or_404(
        RepairOrder.objects.select_related("customer", "vehicle"),
        pk=repair_order_pk,
    )

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


@login_required
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


@login_required
def invoice_issue(request, pk):
    if request.method != "POST":
        return redirect("billing:invoice_detail", pk=pk)

    invoice = get_object_or_404(Invoice.objects.select_related("repair_order"), pk=pk)
    ro = invoice.repair_order

    if invoice.status != Invoice.Status.DRAFT:
        messages.info(
            request,
            f"Invoice {invoice.invoice_number} is already "
            f"{invoice.get_status_display().lower()} — no change made.",
        )
        return redirect("repair_orders:detail", pk=ro.pk)

    invoice.status = Invoice.Status.ISSUED
    if not invoice.issued_at:
        invoice.issued_at = timezone.localdate()
    invoice.updated_by = request.user
    invoice.save(update_fields=["status", "issued_at", "updated_by", "updated_at"])
    messages.success(request, f"Invoice {invoice.invoice_number} issued.")
    return redirect("repair_orders:detail", pk=ro.pk)


@login_required
def invoice_void(request, pk):
    if request.method != "POST":
        return redirect("billing:invoice_detail", pk=pk)

    invoice = get_object_or_404(Invoice.objects.select_related("repair_order"), pk=pk)
    ro = invoice.repair_order

    if invoice.status == Invoice.Status.VOID:
        messages.info(request, f"Invoice {invoice.invoice_number} is already void.")
        return redirect("repair_orders:detail", pk=ro.pk)

    invoice.status = Invoice.Status.VOID
    invoice.updated_by = request.user
    invoice.save(update_fields=["status", "updated_by", "updated_at"])
    messages.success(request, f"Invoice {invoice.invoice_number} voided.")
    return redirect("repair_orders:detail", pk=ro.pk)


@login_required
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

    if invoice.status == Invoice.Status.VOID:
        messages.error(
            request,
            f"Invoice {invoice.invoice_number} is void and cannot accept payments.",
        )
        return redirect("repair_orders:detail", pk=ro.pk)

    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.received_by = request.user
            # Run full model validation now that invoice is set — this catches
            # void-invoice and overpayment constraints defined in Payment.clean().
            try:
                payment.full_clean()
            except ValidationError as e:
                form.add_error(None, e)
            else:
                payment.save()  # also calls invoice.sync_payment_status()
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


@login_required
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

    if request.method == "POST":
        form = InvoiceLineItemForm(request.POST, invoice=invoice)
        if form.is_valid():
            line_item = form.save(commit=False)
            line_item.invoice = invoice
            try:
                line_item.save()
            except ValidationError as e:
                form.add_error(None, e)
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


@login_required
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

    if request.method == "POST":
        form = InvoiceLineItemForm(request.POST, instance=line_item)
        if form.is_valid():
            try:
                form.save()
            except ValidationError as e:
                form.add_error(None, e)
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
