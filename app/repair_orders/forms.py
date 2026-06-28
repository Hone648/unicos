from django import forms
from django.contrib.auth import get_user_model

from .models import RepairOrder


class RepairOrderForm(forms.ModelForm):
    class Meta:
        model = RepairOrder
        fields = [
            "repair_order_number",
            "customer",
            "vehicle",
            "assigned_to",
            "promised_date",
            "reported_problem",
            "internal_notes",
        ]
        widgets = {
            "promised_date": forms.DateInput(attrs={"type": "date"}),
            "reported_problem": forms.Textarea(attrs={"rows": 4}),
            "internal_notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = get_user_model().objects.order_by("username")
        self.fields["assigned_to"].required = False
        self.fields["promised_date"].required = False
        self.fields["reported_problem"].required = False
        self.fields["internal_notes"].required = False

    # Vehicle/customer cross-validation is handled by RepairOrder.clean(), which
    # Django's ModelForm calls automatically via _post_clean() → instance.full_clean().
