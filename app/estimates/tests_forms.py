from decimal import Decimal

from django.test import TestCase

from estimates.forms import EstimateForm
from estimates.models import Estimate


def _form_data(**overrides):
    data = {
        "status": Estimate.Status.DRAFT,
        "insurance_company": "Acme Insurance",
        "claim_number": "CLM-001",
        "deductible": "500.00",
        "estimated_total": "2500.00",
        "notes": "",
    }
    data.update(overrides)
    return data


class EstimateFormTests(TestCase):
    def test_valid_form_passes(self):
        form = EstimateForm(_form_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_blank_insurance_company_is_allowed(self):
        form = EstimateForm(_form_data(insurance_company=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_blank_claim_number_is_allowed(self):
        form = EstimateForm(_form_data(claim_number=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_both_insurance_fields_blank_is_allowed(self):
        # Customer-pay estimates carry no insurance context.
        form = EstimateForm(_form_data(insurance_company="", claim_number=""))
        self.assertTrue(form.is_valid(), form.errors)

    def test_negative_deductible_is_rejected(self):
        form = EstimateForm(_form_data(deductible="-1.00"))
        self.assertFalse(form.is_valid())
        self.assertIn("deductible", form.errors)

    def test_negative_deductible_error_message(self):
        form = EstimateForm(_form_data(deductible="-1.00"))
        self.assertFalse(form.is_valid())
        self.assertIn("cannot be negative", str(form.errors["deductible"]))

    def test_negative_estimated_total_is_rejected(self):
        form = EstimateForm(_form_data(estimated_total="-1.00"))
        self.assertFalse(form.is_valid())
        self.assertIn("estimated_total", form.errors)

    def test_zero_deductible_and_total_are_allowed(self):
        form = EstimateForm(_form_data(deductible="0.00", estimated_total="0.00"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_status_is_rejected(self):
        form = EstimateForm(_form_data(status="not-a-status"))
        self.assertFalse(form.is_valid())
        self.assertIn("status", form.errors)

    def test_form_excludes_repair_order_and_estimate_number(self):
        form = EstimateForm()
        self.assertNotIn("repair_order", form.fields)
        self.assertNotIn("estimate_number", form.fields)
        self.assertNotIn("created_by", form.fields)
        self.assertNotIn("updated_by", form.fields)
