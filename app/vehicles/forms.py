import datetime

from django import forms

from .models import Vehicle

_YEAR_MIN = 1900


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

    def clean_year(self):
        year = self.cleaned_data.get("year")
        if year is not None:
            year_max = datetime.date.today().year + 2
            if year < _YEAR_MIN or year > year_max:
                raise forms.ValidationError(f"Enter a year between {_YEAR_MIN} and {year_max}.")
        return year
