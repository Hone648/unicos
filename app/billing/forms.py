from django import forms

from .models import Invoice, InvoiceLineItem, Payment


class _InvoiceBaseForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "issued_at",
            "due_date",
            "subtotal",
            "tax_amount",
            "notes",
        ]
        widgets = {
            "issued_at": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
    # repair_order, invoice_number, status, created_by, updated_by, created_at,
    # updated_at are excluded. Invoice.clean() validates subtotal/tax >= 0 and
    # due_date >= issued_at via ModelForm._post_clean() -> instance.full_clean().


class InvoiceCreateForm(_InvoiceBaseForm):
    pass


class InvoiceEditForm(_InvoiceBaseForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.line_items.exists():
            self.fields["subtotal"].disabled = True
            self.fields["subtotal"].help_text = (
                "Subtotal is calculated from invoice line items."
            )


class InvoiceLineItemForm(forms.ModelForm):
    def __init__(self, *args, invoice=None, **kwargs):
        super().__init__(*args, **kwargs)
        if invoice is not None and not self.instance.invoice_id:
            self.instance.invoice = invoice
        self.fields["description"].required = True

    class Meta:
        model = InvoiceLineItem
        fields = [
            "item_type",
            "description",
            "quantity",
            "unit_price",
        ]
        widgets = {
            "description": forms.TextInput(),
            "quantity": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "unit_price": forms.NumberInput(attrs={"min": "0.00", "step": "0.01"}),
        }
    # invoice, created_at, and updated_at are excluded.
    # Quantity/unit price and overpayment guards are validated by
    # InvoiceLineItem.clean() via ModelForm._post_clean().


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            "payment_date",
            "amount",
            "method",
            "reference",
            "notes",
        ]
        widgets = {
            "payment_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
    # invoice, received_by, created_at are excluded.
    # Amount > 0 is validated by Payment.clean() via ModelForm._post_clean().
    # Void and overpayment checks require invoice_id to be set; the view calls
    # payment.full_clean() after setting payment.invoice from the URL before saving.
