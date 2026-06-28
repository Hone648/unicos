import datetime
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from core.document_numbers import generate_invoice_number, generate_repair_order_number
from core.models import DocumentNumberSequence

# Use a far-future year so tests never clash with hand-typed existing records.
_FIXED_DATE = datetime.date(2099, 1, 1)
_YEAR = 2099


def _gen_ro():
    with patch("core.document_numbers.timezone") as mock_tz:
        mock_tz.localdate.return_value = _FIXED_DATE
        return generate_repair_order_number()


def _gen_inv():
    with patch("core.document_numbers.timezone") as mock_tz:
        mock_tz.localdate.return_value = _FIXED_DATE
        return generate_invoice_number()


# ---------------------------------------------------------------------------
# Minimal helpers for objects that need full model chains
# ---------------------------------------------------------------------------

def _make_customer():
    from customers.models import Customer
    return Customer.objects.create(
        customer_type=Customer.CustomerType.INDIVIDUAL,
        first_name="Test",
        last_name="User",
    )


def _make_vehicle(customer, vin="1HGBH41JXMN109186"):
    from vehicles.models import Vehicle
    return Vehicle.objects.create(
        customer=customer, vin=vin, make="Honda", model="Civic", year=2021
    )


def _make_ro(customer, vehicle, number="RO-TEST-001"):
    from repair_orders.models import RepairOrder
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number=number
    )


def _make_invoice(ro, number="INV-TEST-001"):
    from billing.models import Invoice
    return Invoice.objects.create(
        repair_order=ro,
        invoice_number=number,
        subtotal=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
    )


# ---------------------------------------------------------------------------
# Repair order number generation
# ---------------------------------------------------------------------------

class GenerateRepairOrderNumberTests(TestCase):
    def test_first_call_returns_formatted_number(self):
        num = _gen_ro()
        self.assertEqual(num, f"RO-{_YEAR}-000001")

    def test_second_call_increments(self):
        _gen_ro()
        num = _gen_ro()
        self.assertEqual(num, f"RO-{_YEAR}-000002")

    def test_creates_sequence_record(self):
        _gen_ro()
        self.assertTrue(
            DocumentNumberSequence.objects.filter(
                document_type=DocumentNumberSequence.DocumentType.REPAIR_ORDER,
                year=_YEAR,
            ).exists()
        )

    def test_initializes_from_existing_matching_ro_numbers(self):
        customer = _make_customer()
        vehicle = _make_vehicle(customer)
        _make_ro(customer, vehicle, number=f"RO-{_YEAR}-000005")
        num = _gen_ro()
        self.assertEqual(num, f"RO-{_YEAR}-000006")

    def test_ignores_nonmatching_legacy_ro_numbers(self):
        customer = _make_customer()
        vehicle = _make_vehicle(customer)
        _make_ro(customer, vehicle, number="RO-LEGACY-99999")
        num = _gen_ro()
        self.assertEqual(num, f"RO-{_YEAR}-000001")

    def test_ignores_other_year_ro_numbers(self):
        customer = _make_customer()
        vehicle = _make_vehicle(customer)
        _make_ro(customer, vehicle, number=f"RO-{_YEAR - 1}-000010")
        num = _gen_ro()
        self.assertEqual(num, f"RO-{_YEAR}-000001")


# ---------------------------------------------------------------------------
# Invoice number generation
# ---------------------------------------------------------------------------

class GenerateInvoiceNumberTests(TestCase):
    def test_first_call_returns_formatted_number(self):
        num = _gen_inv()
        self.assertEqual(num, f"INV-{_YEAR}-000001")

    def test_second_call_increments(self):
        _gen_inv()
        num = _gen_inv()
        self.assertEqual(num, f"INV-{_YEAR}-000002")

    def test_creates_sequence_record(self):
        _gen_inv()
        self.assertTrue(
            DocumentNumberSequence.objects.filter(
                document_type=DocumentNumberSequence.DocumentType.INVOICE,
                year=_YEAR,
            ).exists()
        )

    def test_initializes_from_existing_matching_invoice_numbers(self):
        customer = _make_customer()
        vehicle = _make_vehicle(customer)
        ro = _make_ro(customer, vehicle)
        _make_invoice(ro, number=f"INV-{_YEAR}-000003")
        num = _gen_inv()
        self.assertEqual(num, f"INV-{_YEAR}-000004")

    def test_ignores_nonmatching_legacy_invoice_numbers(self):
        customer = _make_customer()
        vehicle = _make_vehicle(customer)
        ro = _make_ro(customer, vehicle)
        _make_invoice(ro, number="INV-LEGACY-99999")
        num = _gen_inv()
        self.assertEqual(num, f"INV-{_YEAR}-000001")


# ---------------------------------------------------------------------------
# Sequence independence
# ---------------------------------------------------------------------------

class SequenceIndependenceTests(TestCase):
    def test_ro_and_invoice_sequences_are_independent(self):
        with patch("core.document_numbers.timezone") as mock_tz:
            mock_tz.localdate.return_value = _FIXED_DATE
            ro_num = generate_repair_order_number()
            inv_num = generate_invoice_number()
        self.assertEqual(ro_num, f"RO-{_YEAR}-000001")
        self.assertEqual(inv_num, f"INV-{_YEAR}-000001")

    def test_year_boundary_resets_sequence(self):
        with patch("core.document_numbers.timezone") as mock_tz:
            mock_tz.localdate.return_value = _FIXED_DATE
            num_a = generate_repair_order_number()
        with patch("core.document_numbers.timezone") as mock_tz:
            mock_tz.localdate.return_value = datetime.date(_YEAR + 1, 1, 1)
            num_b = generate_repair_order_number()
        self.assertEqual(num_a, f"RO-{_YEAR}-000001")
        self.assertEqual(num_b, f"RO-{_YEAR + 1}-000001")
