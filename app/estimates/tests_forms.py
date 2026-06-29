from decimal import Decimal

from django.test import TestCase

from customers.models import Customer
from estimates.forms import EstimateForm, EstimateLineItemForm
from estimates.models import Estimate, EstimateLineItem
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


def _form_data(**overrides):
    data = {
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

    def test_form_does_not_expose_status(self):
        form = EstimateForm()
        self.assertNotIn("status", form.fields)

    def test_posted_status_is_ignored(self):
        form = EstimateForm(_form_data(status="not-a-status"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("status", form.cleaned_data)

    def test_form_excludes_repair_order_and_estimate_number(self):
        form = EstimateForm()
        self.assertNotIn("repair_order", form.fields)
        self.assertNotIn("estimate_number", form.fields)
        self.assertNotIn("created_by", form.fields)
        self.assertNotIn("updated_by", form.fields)

    def test_form_does_not_expose_kind_or_parent_estimate(self):
        form = EstimateForm()
        self.assertNotIn("kind", form.fields)
        self.assertNotIn("parent_estimate", form.fields)


# ---------------------------------------------------------------------------
# EstimateForm estimated_total disabling
# ---------------------------------------------------------------------------

class EstimateFormTotalDisablingTests(TestCase):
    def setUp(self):
        customer = Customer.objects.create(
            customer_type=Customer.CustomerType.INDIVIDUAL,
            first_name="Form", last_name="Total",
        )
        vehicle = Vehicle.objects.create(
            customer=customer, vin=VALID_VIN, make="Honda", model="Civic", year=2020,
        )
        self.ro = RepairOrder.objects.create(
            customer=customer, vehicle=vehicle, repair_order_number="RO-FORM-TOTAL",
        )
        self.estimate = Estimate.objects.create(
            repair_order=self.ro, estimate_number="EST-FORM-TOTAL",
        )

    def test_estimated_total_enabled_without_line_items(self):
        form = EstimateForm(instance=self.estimate)
        self.assertFalse(form.fields["estimated_total"].disabled)

    def test_estimated_total_disabled_with_line_items(self):
        EstimateLineItem.objects.create(
            estimate=self.estimate,
            description="Labor", quantity=Decimal("1.00"), unit_price=Decimal("100.00"),
        )
        form = EstimateForm(instance=self.estimate)
        self.assertTrue(form.fields["estimated_total"].disabled)

    def test_disabled_total_has_help_text(self):
        EstimateLineItem.objects.create(
            estimate=self.estimate,
            description="Labor", quantity=Decimal("1.00"), unit_price=Decimal("100.00"),
        )
        form = EstimateForm(instance=self.estimate)
        self.assertIn("calculated", form.fields["estimated_total"].help_text.lower())


# ---------------------------------------------------------------------------
# EstimateLineItemForm
# ---------------------------------------------------------------------------

def _line_item_data(**overrides):
    data = {
        "item_type": EstimateLineItem.ItemType.LABOR,
        "description": "Labor hours",
        "quantity": "2.00",
        "unit_price": "75.00",
    }
    data.update(overrides)
    return data


class EstimateLineItemFormTests(TestCase):
    def test_valid_form_passes(self):
        form = EstimateLineItemForm(_line_item_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_zero_quantity_rejected(self):
        form = EstimateLineItemForm(_line_item_data(quantity="0.00"))
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)
        self.assertIn("greater than zero", str(form.errors["quantity"]))

    def test_negative_quantity_rejected(self):
        form = EstimateLineItemForm(_line_item_data(quantity="-1.00"))
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_negative_unit_price_rejected(self):
        form = EstimateLineItemForm(_line_item_data(unit_price="-1.00"))
        self.assertFalse(form.is_valid())
        self.assertIn("unit_price", form.errors)
        self.assertIn("cannot be negative", str(form.errors["unit_price"]))

    def test_zero_unit_price_accepted(self):
        form = EstimateLineItemForm(_line_item_data(unit_price="0.00"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_blank_description_rejected(self):
        form = EstimateLineItemForm(_line_item_data(description=""))
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)

    def test_whitespace_description_rejected(self):
        form = EstimateLineItemForm(_line_item_data(description="   "))
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)

    def test_description_is_stripped(self):
        form = EstimateLineItemForm(_line_item_data(description="  Labor  "))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["description"], "Labor")

    def test_form_excludes_estimate_and_sort_order(self):
        form = EstimateLineItemForm()
        self.assertNotIn("estimate", form.fields)
        self.assertNotIn("sort_order", form.fields)
