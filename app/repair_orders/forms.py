from django import forms
from django.contrib.auth import get_user_model
from django.urls import reverse_lazy
from vehicles.models import Vehicle

from .models import RepairOrder


class _RepairOrderBaseForm(forms.ModelForm):
    class Meta:
        model = RepairOrder
        fields = [
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

    def __init__(self, *args, customer_id=None, enable_vehicle_htmx=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = get_user_model().objects.order_by("username")
        self.fields["assigned_to"].required = False
        self.fields["promised_date"].required = False
        self.fields["reported_problem"].required = False
        self.fields["internal_notes"].required = False
        if enable_vehicle_htmx:
            self.fields["customer"].widget.attrs.update(
                {
                    "hx-get": reverse_lazy("repair_orders:vehicle_field"),
                    "hx-target": "#vehicle-field",
                    "hx-trigger": "change",
                    "hx-swap": "outerHTML",
                }
            )

        selected_customer_id = self._selected_customer_id(customer_id)
        self._scope_vehicle_field(selected_customer_id)

    def _selected_customer_id(self, customer_id):
        if customer_id:
            return customer_id
        if self.is_bound:
            return self.data.get(self.add_prefix("customer")) or None
        if self.instance and self.instance.customer_id:
            return self.instance.customer_id
        return None

    def _scope_vehicle_field(self, customer_id):
        vehicle_field = self.fields["vehicle"]
        vehicle_field.empty_label = "Select a customer first"
        vehicle_field.queryset = Vehicle.objects.none()
        vehicle_field.widget.attrs["disabled"] = "disabled"

        if not customer_id:
            return

        try:
            customer_pk = int(customer_id)
        except (TypeError, ValueError):
            return

        vehicles = Vehicle.objects.filter(customer_id=customer_pk).order_by("make", "model", "vin")
        if vehicles.exists():
            vehicle_field.empty_label = "Select a vehicle"
            vehicle_field.queryset = vehicles
            vehicle_field.widget.attrs.pop("disabled", None)
            return

        vehicle_field.empty_label = "No vehicles found for this customer"

    # Vehicle/customer cross-validation is handled by RepairOrder.clean(), which
    # Django's ModelForm calls automatically via _post_clean() → instance.full_clean().


class RepairOrderCreateForm(_RepairOrderBaseForm):
    pass


class RepairOrderEditForm(_RepairOrderBaseForm):
    pass
