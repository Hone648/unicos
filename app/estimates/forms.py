from decimal import Decimal

from django import forms

from .models import Estimate


class EstimateForm(forms.ModelForm):
    class Meta:
        model = Estimate
        fields = [
            "status",
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
    # repair_order, estimate_number, created_by, updated_by, and timestamps are
    # excluded. The view assigns repair_order (from the URL) and the generated
    # estimate_number on create. insurance_company and claim_number may be blank
    # because customer-pay estimates do not have insurance context.

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
