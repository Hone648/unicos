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

    def __init__(
        self, *args, customer_id=None, enable_vehicle_htmx=False, vehicle_queryset=None, **kwargs
    ):
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
        self._scope_vehicle_field(selected_customer_id, vehicle_queryset)

    def _selected_customer_id(self, customer_id):
        if customer_id:
            return customer_id
        if self.is_bound:
            return self.data.get(self.add_prefix("customer")) or None
        if self.instance and self.instance.customer_id:
            return self.instance.customer_id
        return None

    def _scope_vehicle_field(self, customer_id, vehicle_queryset):
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

        if vehicle_queryset is None:
            vehicle_queryset = Vehicle.objects.all()
        vehicles = vehicle_queryset.filter(customer_id=customer_pk)
        if vehicles.exists():
            vehicle_field.empty_label = "Select a vehicle"
            vehicle_field.queryset = vehicles
            vehicle_field.widget.attrs.pop("disabled", None)
            return

        vehicle_field.empty_label = "No vehicles found for this customer"

    # Vehicle/customer cross-validation is handled by RepairOrder.clean(), which
    # Django's ModelForm calls automatically via _post_clean() → instance.full_clean().


class _IntakeVehicleChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, vehicle):
        description = " ".join(
            str(part) for part in (vehicle.year, vehicle.make, vehicle.model) if part
        )
        return f"{vehicle.vin} — {description}"


class RepairOrderCreateForm(_RepairOrderBaseForm):
    class Meta(_RepairOrderBaseForm.Meta):
        field_classes = {"vehicle": _IntakeVehicleChoiceField}

    @property
    def vehicle_choices(self):
        return self.fields["vehicle"].queryset

    def __init__(
        self, *args, intake_customer=None, intake_vehicle=None, enable_vehicle_htmx=False, **kwargs
    ):
        if intake_customer is None:
            super().__init__(*args, enable_vehicle_htmx=enable_vehicle_htmx, **kwargs)
            return

        vehicles = intake_customer.vehicles.filter(is_active=True)
        if intake_vehicle is not None:
            vehicles = vehicles.filter(pk=intake_vehicle.pk)
        vehicle_ids = list(vehicles.values_list("pk", flat=True)[:2])
        self.has_intake_vehicles = bool(vehicle_ids)

        initial = {"customer": intake_customer.pk}
        if len(vehicle_ids) == 1:
            initial["vehicle"] = vehicle_ids[0]
        super().__init__(
            *args,
            customer_id=intake_customer.pk,
            initial=initial,
            vehicle_queryset=vehicles,
            **kwargs,
        )
        customer_field = self.fields["customer"]
        customer_field.queryset = customer_field.queryset.filter(pk=intake_customer.pk)


class RepairOrderEditForm(_RepairOrderBaseForm):
    pass
