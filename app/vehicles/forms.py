from django import forms

from .models import Vehicle


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            "vin",
            "year",
            "make",
            "model",
            "trim",
            "color",
            "license_plate",
            "license_state",
            "odometer",
            "notes",
            "is_active",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
    # Customer is excluded from the form; the view sets it from the URL for create,
    # and edit preserves the existing customer via the instance.
    # VIN normalization (strip + uppercase) is handled by Vehicle.clean_fields(),
    # called automatically via ModelForm._post_clean() -> instance.full_clean().
