from datetime import date
from decimal import Decimal

from billing.forms import InvoiceLineItemForm, PaymentForm
from billing.models import Invoice, InvoiceLineItem, Payment
from customers.models import Customer
from django.test import TestCase
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_invoice():
    customer = Customer.objects.create(
        customer_type=Customer.CustomerType.INDIVIDUAL,
        first_name="Form",
        last_name="Test",
    )
    vehicle = Vehicle.objects.create(
        customer=customer,
        vin=VALID_VIN,
        make="Honda",
        model="Civic",
        year=2020,
    )
    ro = RepairOrder.objects.create(
        customer=customer,
        vehicle=vehicle,
        repair_order_number="RO-FORM-001",
    )
    return Invoice.objects.create(
        repair_order=ro,
        invoice_number="INV-FORM-001",
        subtotal=Decimal("500.00"),
        tax_amount=Decimal("0.00"),
    )


# ---------------------------------------------------------------------------
# InvoiceLineItemForm — quantity validation
# ---------------------------------------------------------------------------


class LineItemQuantityValidationTests(TestCase):
    def setUp(self):
        self.invoice = _make_invoice()

    def _data(self, **overrides):
        data = {
            "item_type": InvoiceLineItem.ItemType.LABOR,
            "description": "Labor hours",
            "quantity": "2.00",
            "unit_price": "75.00",
        }
        data.update(overrides)
        return data

    def test_valid_quantity_passes(self):
        form = InvoiceLineItemForm(self._data(), invoice=self.invoice)
        self.assertTrue(form.is_valid(), form.errors)

    def test_zero_quantity_is_rejected(self):
        form = InvoiceLineItemForm(self._data(quantity="0.00"), invoice=self.invoice)
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_negative_quantity_is_rejected(self):
        form = InvoiceLineItemForm(self._data(quantity="-1.00"), invoice=self.invoice)
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_zero_quantity_error_message(self):
        form = InvoiceLineItemForm(self._data(quantity="0.00"), invoice=self.invoice)
        self.assertFalse(form.is_valid())
        self.assertIn("greater than zero", str(form.errors["quantity"]))

    def test_minimum_valid_quantity_passes(self):
        form = InvoiceLineItemForm(self._data(quantity="0.01"), invoice=self.invoice)
        self.assertTrue(form.is_valid(), form.errors)


# ---------------------------------------------------------------------------
# InvoiceLineItemForm — unit price validation
# ---------------------------------------------------------------------------


class LineItemUnitPriceValidationTests(TestCase):
    def setUp(self):
        self.invoice = _make_invoice()

    def _data(self, **overrides):
        data = {
            "item_type": InvoiceLineItem.ItemType.PARTS,
            "description": "Part",
            "quantity": "1.00",
            "unit_price": "50.00",
        }
        data.update(overrides)
        return data

    def test_valid_unit_price_passes(self):
        form = InvoiceLineItemForm(self._data(), invoice=self.invoice)
        self.assertTrue(form.is_valid(), form.errors)

    def test_zero_unit_price_is_accepted(self):
        # Zero price is allowed (e.g., warranty coverage)
        form = InvoiceLineItemForm(self._data(unit_price="0.00"), invoice=self.invoice)
        self.assertTrue(form.is_valid(), form.errors)

    def test_negative_unit_price_is_rejected(self):
        form = InvoiceLineItemForm(self._data(unit_price="-1.00"), invoice=self.invoice)
        self.assertFalse(form.is_valid())
        self.assertIn("unit_price", form.errors)

    def test_negative_unit_price_error_message(self):
        form = InvoiceLineItemForm(self._data(unit_price="-0.01"), invoice=self.invoice)
        self.assertFalse(form.is_valid())
        self.assertIn("cannot be negative", str(form.errors["unit_price"]))


# ---------------------------------------------------------------------------
# InvoiceLineItemForm — description validation
# ---------------------------------------------------------------------------


class LineItemDescriptionValidationTests(TestCase):
    def setUp(self):
        self.invoice = _make_invoice()

    def _data(self, **overrides):
        data = {
            "item_type": InvoiceLineItem.ItemType.LABOR,
            "description": "Valid description",
            "quantity": "1.00",
            "unit_price": "100.00",
        }
        data.update(overrides)
        return data

    def test_blank_description_is_rejected(self):
        form = InvoiceLineItemForm(self._data(description=""), invoice=self.invoice)
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)

    def test_whitespace_only_description_is_rejected(self):
        # Django CharField strips whitespace by default; stripped empty = required error
        form = InvoiceLineItemForm(self._data(description="   "), invoice=self.invoice)
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)


# ---------------------------------------------------------------------------
# PaymentForm — amount validation
# ---------------------------------------------------------------------------


class PaymentAmountValidationTests(TestCase):
    def _data(self, **overrides):
        data = {
            "payment_date": str(date.today()),
            "amount": "100.00",
            "method": Payment.Method.CASH,
            "reference": "",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_valid_amount_passes(self):
        form = PaymentForm(self._data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_zero_amount_is_rejected(self):
        form = PaymentForm(self._data(amount="0.00"))
        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_negative_amount_is_rejected(self):
        form = PaymentForm(self._data(amount="-1.00"))
        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_zero_amount_error_message(self):
        form = PaymentForm(self._data(amount="0.00"))
        self.assertFalse(form.is_valid())
        self.assertIn("greater than zero", str(form.errors["amount"]))

    def test_small_valid_amount_passes(self):
        form = PaymentForm(self._data(amount="0.01"))
        self.assertTrue(form.is_valid(), form.errors)
