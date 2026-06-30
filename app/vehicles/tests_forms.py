import datetime

from django.test import TestCase
from vehicles.forms import VehicleForm

VALID_VIN = "1HGBH41JXMN109186"
CURRENT_YEAR = datetime.date.today().year


def _form_data(**overrides):
    data = {
        "vin": VALID_VIN,
        "year": str(CURRENT_YEAR - 5),
        "make": "Honda",
        "model": "Accord",
        "trim": "",
        "color": "",
        "license_plate": "",
        "license_state": "",
        "odometer": "",
        "notes": "",
        "is_active": "on",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Vehicle year validation
# ---------------------------------------------------------------------------


class VehicleYearValidationTests(TestCase):
    def test_valid_year_is_accepted(self):
        form = VehicleForm(_form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_year_at_lower_bound_is_valid(self):
        form = VehicleForm(_form_data(year="1900"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_year_at_upper_bound_is_valid(self):
        form = VehicleForm(_form_data(year=str(CURRENT_YEAR + 2)))
        self.assertTrue(form.is_valid(), form.errors)

    def test_year_below_1900_is_rejected(self):
        form = VehicleForm(_form_data(year="1899"))
        self.assertFalse(form.is_valid())
        self.assertIn("year", form.errors)

    def test_year_above_limit_is_rejected(self):
        form = VehicleForm(_form_data(year=str(CURRENT_YEAR + 3)))
        self.assertFalse(form.is_valid())
        self.assertIn("year", form.errors)

    def test_year_error_mentions_bounds(self):
        form = VehicleForm(_form_data(year="1899"))
        self.assertFalse(form.is_valid())
        self.assertIn("1900", str(form.errors["year"]))

    def test_blank_year_is_accepted(self):
        # year is nullable on the model; blank is allowed
        form = VehicleForm(_form_data(year=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_year_zero_is_rejected(self):
        form = VehicleForm(_form_data(year="0"))
        self.assertFalse(form.is_valid())
        self.assertIn("year", form.errors)
