from billing.models import Invoice
from django import forms
from estimates.models import Estimate
from repair_orders.models import RepairOrder

ALL_STATUSES = "all"


class ReportFilterForm(forms.Form):
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    repair_order_status = forms.ChoiceField(
        required=False,
        choices=[(ALL_STATUSES, "All statuses")] + list(RepairOrder.Status.choices),
    )
    invoice_status = forms.ChoiceField(
        required=False,
        choices=[(ALL_STATUSES, "All statuses")] + list(Invoice.Status.choices),
    )
    estimate_status = forms.ChoiceField(
        required=False,
        choices=[(ALL_STATUSES, "All statuses")] + list(Estimate.Status.choices),
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Start date cannot be after end date.")

        for field_name in ["repair_order_status", "invoice_status", "estimate_status"]:
            if not cleaned_data.get(field_name):
                cleaned_data[field_name] = ALL_STATUSES

        return cleaned_data
