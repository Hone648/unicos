from django import forms

from .models import Invoice, Payment


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "invoice_number",
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
    # repair_order, status, created_by, updated_by, created_at, updated_at are excluded.
    # Invoice.clean() validates subtotal/tax >= 0 and due_date >= issued_at via
    # ModelForm._post_clean() -> instance.full_clean().


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
