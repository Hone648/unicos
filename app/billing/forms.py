from core.tax import default_taxable_for_item_type
from core.tax_review import TaxReviewLineItemForm
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
        if self.instance.has_line_items:
            self.fields["subtotal"].disabled = True
            self.fields["subtotal"].help_text = "Subtotal is calculated from invoice line items."
            self.fields["tax_amount"].disabled = True
            if self.instance.tax_breakdown_recorded:
                self.fields["tax_amount"].help_text = "Tax is calculated from invoice line items."
            else:
                self.fields["tax_amount"].help_text = "Saved tax for this itemized invoice."


class InvoiceLineItemForm(TaxReviewLineItemForm):
    def __init__(self, *args, invoice=None, **kwargs):
        super().__init__(*args, **kwargs)
        if invoice is not None and not self.instance.invoice_id:
            self.instance.invoice = invoice
        self.fields["description"].required = True
        # Seed the Texas default taxability from item type for new line items.
        # An explicitly bound value from POST always wins over this initial.
        if self.instance.invoice_id and not self.instance.invoice.tax_breakdown_recorded:
            self.fields.pop("is_taxable", None)
        elif not self.is_bound and self.instance.pk is None and "is_taxable" in self.fields:
            item_type = self.initial.get("item_type") or self.fields["item_type"].initial
            if item_type is None:
                item_type = InvoiceLineItem.ItemType.LABOR
            self.fields["is_taxable"].initial = default_taxable_for_item_type(item_type)

    class Meta:
        model = InvoiceLineItem
        fields = [
            "item_type",
            "description",
            "quantity",
            "unit_price",
            "is_taxable",
        ]
        widgets = {
            "description": forms.TextInput(),
            "quantity": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "unit_price": forms.NumberInput(attrs={"min": "0.00", "step": "0.01"}),
        }
        labels = {
            "is_taxable": "Taxable",
        }
        help_texts = {
            "is_taxable": (
                "Texas default: labor is not taxable; parts/materials are taxable. "
                "Verify unusual sublet or misc charges."
            ),
        }

    # invoice, created_at, and updated_at are excluded.
    # Quantity/unit price guards below fire at field-clean time (before _post_clean),
    # giving field-attached error messages instead of the generic MinValueValidator text.

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return quantity

    def clean_unit_price(self):
        price = self.cleaned_data.get("unit_price")
        if price is not None and price < 0:
            raise forms.ValidationError("Unit price cannot be negative.")
        return price


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
    # Void and overpayment checks require invoice_id to be set; the view calls
    # payment.full_clean() after setting payment.invoice from the URL before saving.
    # clean_amount fires at field-clean time so the error attaches to the amount field.

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount
