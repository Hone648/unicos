from decimal import Decimal

from core.tax import default_taxable_for_item_type
from core.tax_review import TaxReviewLineItemForm
from django import forms

from .models import Estimate, EstimateLineItem


class EstimateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Once an estimate has line items, estimated_total is calculated from
        # them and must not be edited by hand (mirrors the billing invoice
        # subtotal pattern). A disabled field keeps the instance value on POST.
        if self.instance.pk and self.instance.line_items.exists():
            self.fields["estimated_total"].disabled = True
            self.fields[
                "estimated_total"
            ].help_text = "Estimated total is calculated from estimate line items."

    class Meta:
        model = Estimate
        fields = [
            "insurance_company",
            "claim_number",
            "deductible",
            "estimated_total",
            "notes",
        ]
        widgets = {
            "deductible": forms.NumberInput(attrs={"min": "0.00", "step": "0.01"}),
            "estimated_total": forms.NumberInput(attrs={"min": "0.00", "step": "0.01"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    # status, repair_order, estimate_number, kind, parent_estimate, created_by,
    # updated_by, and timestamps are excluded. Status changes use explicit
    # lifecycle actions; the view assigns repair_order, the generated
    # estimate_number, and (for supplements) kind/parent_estimate. Insurance
    # company and claim number may be blank because customer-pay estimates do
    # not have insurance context.

    def clean_deductible(self):
        deductible = self.cleaned_data.get("deductible")
        if deductible is not None and deductible < Decimal("0.00"):
            raise forms.ValidationError("Deductible cannot be negative.")
        return deductible

    def clean_estimated_total(self):
        total = self.cleaned_data.get("estimated_total")
        if total is not None and total < Decimal("0.00"):
            raise forms.ValidationError("Estimated total cannot be negative.")
        return total


class EstimateLineItemForm(TaxReviewLineItemForm):
    def __init__(self, *args, estimate=None, **kwargs):
        super().__init__(*args, **kwargs)
        # For a new (unbound, unsaved) line item, seed the Texas default
        # taxability from the item type so the checkbox starts correct. An
        # explicitly bound value from POST always wins over this initial.
        if estimate is not None and not self.instance.estimate_id:
            self.instance.estimate = estimate
        estimate = self.instance.estimate if self.instance.estimate_id else None
        if estimate is not None and not estimate.tax_breakdown_recorded:
            self.fields.pop("is_taxable", None)
        elif not self.is_bound and self.instance.pk is None and "is_taxable" in self.fields:
            item_type = self.initial.get("item_type") or self.fields["item_type"].initial
            if item_type is None:
                item_type = EstimateLineItem.ItemType.LABOR
            self.fields["is_taxable"].initial = default_taxable_for_item_type(item_type)

    class Meta:
        model = EstimateLineItem
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

    # estimate, sort_order, and timestamps are excluded. The view assigns the
    # estimate from the URL; sort_order defaults to 0. Field-level clean methods
    # below give field-attached error messages.

    def clean_description(self):
        description = self.cleaned_data.get("description", "")
        if not description or not description.strip():
            raise forms.ValidationError("Description is required.")
        return description.strip()

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity is not None and quantity <= Decimal("0.00"):
            raise forms.ValidationError("Quantity must be greater than zero.")
        return quantity

    def clean_unit_price(self):
        price = self.cleaned_data.get("unit_price")
        if price is not None and price < Decimal("0.00"):
            raise forms.ValidationError("Unit price cannot be negative.")
        return price


class EstimateApprovalForm(forms.ModelForm):
    class Meta:
        model = Estimate
        fields = [
            "approval_source",
            "approval_contact_name",
            "approval_reference",
            "approval_note",
        ]
        widgets = {
            "approval_note": forms.Textarea(attrs={"rows": 2}),
        }

    def clean_approval_source(self):
        source = self.cleaned_data.get("approval_source")
        if not source:
            raise forms.ValidationError("Approval source is required.")
        return source

    def clean_approval_contact_name(self):
        name = self.cleaned_data.get("approval_contact_name", "")
        if not name or not name.strip():
            raise forms.ValidationError("Approval contact name is required.")
        return name.strip()

    def clean_approval_reference(self):
        return (self.cleaned_data.get("approval_reference") or "").strip()

    def clean_approval_note(self):
        return (self.cleaned_data.get("approval_note") or "").strip()
