from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from billing.models import Invoice, InvoiceLineItem
from billing.services import (
    EstimateInvoiceConversionBlocked,
    convert_estimate_to_invoice,
    estimate_can_convert_to_invoice,
)
from customers.models import Customer
from estimates.models import Estimate, EstimateLineItem
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


def make_repair_order(number="RO-CONV-001"):
    customer = Customer.objects.create(
        customer_type=Customer.CustomerType.INDIVIDUAL,
        first_name="Conv",
        last_name="Test",
    )
    vehicle = Vehicle.objects.create(
        customer=customer,
        vin=VALID_VIN,
        make="Honda",
        model="Civic",
        year=2021,
    )
    return RepairOrder.objects.create(
        customer=customer,
        vehicle=vehicle,
        repair_order_number=number,
    )


def make_estimate(repair_order, number="EST-CONV-001", status=Estimate.Status.APPROVED):
    return Estimate.objects.create(
        repair_order=repair_order,
        estimate_number=number,
        status=status,
    )


def add_line_item(estimate, **kwargs):
    defaults = {
        "item_type": EstimateLineItem.ItemType.LABOR,
        "description": "Refinish",
        "quantity": Decimal("2.00"),
        "unit_price": Decimal("75.00"),
    }
    defaults.update(kwargs)
    return EstimateLineItem.objects.create(estimate=estimate, **defaults)


class ConvertEstimateToInvoiceTests(TestCase):
    def setUp(self):
        self.ro = make_repair_order()
        self.estimate = make_estimate(self.ro)
        add_line_item(self.estimate, description="Body labor", quantity=Decimal("2.00"), unit_price=Decimal("75.00"))
        add_line_item(self.estimate, item_type=EstimateLineItem.ItemType.PARTS, description="Bumper", quantity=Decimal("1.00"), unit_price=Decimal("300.00"))
        self.estimate.refresh_from_db()
        self.user = get_user_model().objects.create_user(
            username="conv-user", password="pw-test-12345"
        )

    def test_approved_estimate_converts_to_draft_invoice(self):
        invoice = convert_estimate_to_invoice(self.estimate, created_by=self.user)
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)
        self.assertIsNotNone(invoice.invoice_number)

    def test_invoice_linked_to_same_repair_order(self):
        invoice = convert_estimate_to_invoice(self.estimate, created_by=self.user)
        self.assertEqual(invoice.repair_order, self.ro)

    def test_invoice_source_estimate_is_set(self):
        invoice = convert_estimate_to_invoice(self.estimate, created_by=self.user)
        self.assertEqual(invoice.source_estimate, self.estimate)

    def test_invoice_number_matches_pattern(self):
        invoice = convert_estimate_to_invoice(self.estimate, created_by=self.user)
        self.assertRegex(invoice.invoice_number, r"^INV-\d{4}-\d{6}$")

    def test_line_items_are_copied(self):
        invoice = convert_estimate_to_invoice(self.estimate, created_by=self.user)
        items = list(invoice.line_items.order_by("id"))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].description, "Body labor")
        self.assertEqual(items[0].quantity, Decimal("2.00"))
        self.assertEqual(items[0].unit_price, Decimal("75.00"))
        self.assertEqual(items[1].item_type, InvoiceLineItem.ItemType.PARTS)
        self.assertEqual(items[1].description, "Bumper")

    def test_invoice_total_matches_estimate_total(self):
        invoice = convert_estimate_to_invoice(self.estimate, created_by=self.user)
        # 2 * 75 + 1 * 300 = 450
        self.assertEqual(self.estimate.estimated_total, Decimal("450.00"))
        self.assertEqual(invoice.subtotal, Decimal("450.00"))
        self.assertEqual(invoice.total_amount, self.estimate.estimated_total)

    def test_created_by_and_updated_by_are_set(self):
        invoice = convert_estimate_to_invoice(self.estimate, created_by=self.user)
        self.assertEqual(invoice.created_by, self.user)
        self.assertEqual(invoice.updated_by, self.user)

    def test_estimate_status_is_not_mutated(self):
        convert_estimate_to_invoice(self.estimate, created_by=self.user)
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.status, Estimate.Status.APPROVED)

    def test_can_convert_predicate_true_for_approved_with_line_items(self):
        self.assertTrue(estimate_can_convert_to_invoice(self.estimate))


class ConvertBlockedTests(TestCase):
    def setUp(self):
        self.ro = make_repair_order()
        self.user = get_user_model().objects.create_user(
            username="conv-blocked", password="pw-test-12345"
        )

    def _approved_with_items(self, number="EST-OK"):
        estimate = make_estimate(self.ro, number=number)
        add_line_item(estimate)
        estimate.refresh_from_db()
        return estimate

    def test_draft_estimate_is_blocked(self):
        estimate = make_estimate(self.ro, status=Estimate.Status.DRAFT)
        add_line_item(estimate)
        with self.assertRaises(EstimateInvoiceConversionBlocked):
            convert_estimate_to_invoice(estimate, created_by=self.user)
        self.assertFalse(Invoice.objects.exists())

    def test_submitted_estimate_is_blocked(self):
        estimate = make_estimate(self.ro, status=Estimate.Status.SUBMITTED)
        add_line_item(estimate)
        with self.assertRaises(EstimateInvoiceConversionBlocked):
            convert_estimate_to_invoice(estimate, created_by=self.user)
        self.assertFalse(Invoice.objects.exists())

    def test_declined_estimate_is_blocked(self):
        estimate = make_estimate(self.ro, status=Estimate.Status.DECLINED)
        add_line_item(estimate)
        with self.assertRaises(EstimateInvoiceConversionBlocked):
            convert_estimate_to_invoice(estimate, created_by=self.user)
        self.assertFalse(Invoice.objects.exists())

    def test_expired_estimate_is_blocked(self):
        estimate = make_estimate(self.ro, status=Estimate.Status.EXPIRED)
        add_line_item(estimate)
        with self.assertRaises(EstimateInvoiceConversionBlocked):
            convert_estimate_to_invoice(estimate, created_by=self.user)
        self.assertFalse(Invoice.objects.exists())

    def test_approved_without_line_items_is_blocked(self):
        estimate = make_estimate(self.ro, status=Estimate.Status.APPROVED)
        with self.assertRaises(EstimateInvoiceConversionBlocked):
            convert_estimate_to_invoice(estimate, created_by=self.user)
        self.assertFalse(Invoice.objects.exists())

    def test_duplicate_conversion_is_blocked(self):
        estimate = self._approved_with_items()
        convert_estimate_to_invoice(estimate, created_by=self.user)
        with self.assertRaises(EstimateInvoiceConversionBlocked):
            convert_estimate_to_invoice(estimate, created_by=self.user)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_conversion_blocked_when_ro_already_has_invoice(self):
        # A manually-created invoice already occupies the one-to-one slot.
        Invoice.objects.create(
            repair_order=self.ro,
            invoice_number="INV-MANUAL-1",
            status=Invoice.Status.DRAFT,
        )
        estimate = self._approved_with_items(number="EST-RO-TAKEN")
        with self.assertRaises(EstimateInvoiceConversionBlocked):
            convert_estimate_to_invoice(estimate, created_by=self.user)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_predicate_false_for_blocked_estimate(self):
        estimate = make_estimate(self.ro, status=Estimate.Status.DRAFT)
        add_line_item(estimate)
        self.assertFalse(estimate_can_convert_to_invoice(estimate))
