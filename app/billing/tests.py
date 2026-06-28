from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from billing.models import Invoice, Payment
from customers.models import Customer
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_customer(**kwargs):
    defaults = {
        "customer_type": Customer.CustomerType.INDIVIDUAL,
        "first_name": "Test",
        "last_name": "Customer",
    }
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


def make_vehicle(customer, vin=VALID_VIN, **kwargs):
    return Vehicle.objects.create(
        customer=customer, vin=vin, make="Honda", model="Civic", year=2021, **kwargs
    )


def make_repair_order(customer, vehicle, number="RO-0001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number=number, **kwargs
    )


def make_invoice(repair_order, number="INV-001", **kwargs):
    defaults = {"subtotal": Decimal("500.00"), "tax_amount": Decimal("50.00")}
    defaults.update(kwargs)
    return Invoice.objects.create(
        repair_order=repair_order, invoice_number=number, **defaults
    )


def make_payment(invoice, amount=Decimal("100.00"), **kwargs):
    from datetime import date
    defaults = {"payment_date": date.today(), "method": Payment.Method.CASH}
    defaults.update(kwargs)
    return Payment.objects.create(invoice=invoice, amount=amount, **defaults)


# ---------------------------------------------------------------------------
# Invoice model tests
# ---------------------------------------------------------------------------

class InvoiceModelTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_can_create_invoice_linked_to_repair_order(self):
        inv = make_invoice(self.ro)
        self.assertIsNotNone(inv.pk)
        self.assertEqual(inv.repair_order, self.ro)

    def test_one_repair_order_cannot_have_two_invoices(self):
        make_invoice(self.ro)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Invoice.objects.create(
                repair_order=self.ro,
                invoice_number="INV-DUP",
                subtotal=Decimal("0.00"),
                tax_amount=Decimal("0.00"),
            )

    def test_negative_subtotal_fails_validation(self):
        inv = Invoice(
            repair_order=self.ro,
            invoice_number="INV-NEG",
            subtotal=Decimal("-1.00"),
            tax_amount=Decimal("0.00"),
        )
        with self.assertRaises(ValidationError):
            inv.full_clean()

    def test_negative_tax_amount_fails_validation(self):
        inv = Invoice(
            repair_order=self.ro,
            invoice_number="INV-NEGTAX",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("-5.00"),
        )
        with self.assertRaises(ValidationError):
            inv.full_clean()

    def test_total_amount_equals_subtotal_plus_tax(self):
        inv = make_invoice(self.ro, subtotal=Decimal("500.00"), tax_amount=Decimal("50.00"))
        self.assertEqual(inv.total_amount, Decimal("550.00"))

    def test_amount_paid_sums_payments(self):
        inv = make_invoice(self.ro)
        make_payment(inv, Decimal("100.00"))
        make_payment(inv, Decimal("200.00"))
        self.assertEqual(inv.amount_paid, Decimal("300.00"))

    def test_balance_due_subtracts_payments(self):
        inv = make_invoice(self.ro, subtotal=Decimal("500.00"), tax_amount=Decimal("50.00"))
        make_payment(inv, Decimal("300.00"))
        self.assertEqual(inv.balance_due, Decimal("250.00"))

    def test_is_paid_true_when_fully_paid(self):
        inv = make_invoice(self.ro, subtotal=Decimal("100.00"), tax_amount=Decimal("0.00"))
        make_payment(inv, Decimal("100.00"))
        self.assertTrue(inv.is_paid)

    def test_is_paid_false_when_not_fully_paid(self):
        inv = make_invoice(self.ro, subtotal=Decimal("100.00"), tax_amount=Decimal("0.00"))
        make_payment(inv, Decimal("50.00"))
        self.assertFalse(inv.is_paid)

    def test_due_date_before_issued_at_fails_validation(self):
        from datetime import date
        inv = Invoice(
            repair_order=self.ro,
            invoice_number="INV-DATE",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
            issued_at=date(2026, 6, 1),
            due_date=date(2026, 5, 1),
        )
        with self.assertRaises(ValidationError):
            inv.full_clean()


# ---------------------------------------------------------------------------
# Payment model tests
# ---------------------------------------------------------------------------

class PaymentModelTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.invoice = make_invoice(self.ro, subtotal=Decimal("500.00"), tax_amount=Decimal("0.00"))

    def test_can_create_payment_linked_to_invoice(self):
        p = make_payment(self.invoice, Decimal("100.00"))
        self.assertIsNotNone(p.pk)
        self.assertEqual(p.invoice, self.invoice)

    def test_zero_amount_fails_validation(self):
        p = Payment(invoice=self.invoice, amount=Decimal("0.00"))
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_negative_amount_fails_validation(self):
        p = Payment(invoice=self.invoice, amount=Decimal("-10.00"))
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_cannot_create_payment_for_void_invoice(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])
        p = Payment(invoice=self.invoice, amount=Decimal("50.00"))
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_payment_cannot_exceed_invoice_balance(self):
        # Invoice total is 500; try to pay 600
        p = Payment(invoice=self.invoice, amount=Decimal("600.00"))
        with self.assertRaises(ValidationError):
            p.full_clean()

    def test_partial_payment_sets_invoice_to_partially_paid(self):
        make_payment(self.invoice, Decimal("250.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)

    def test_full_payment_sets_invoice_to_paid(self):
        make_payment(self.invoice, Decimal("500.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

    def test_deleting_payment_resyncs_invoice_status_to_draft_when_no_issued_at(self):
        # No issued_at on self.invoice — fallback should be DRAFT.
        p = make_payment(self.invoice, Decimal("500.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        p.delete()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.DRAFT)

    def test_deleting_payment_from_paid_invoice_with_issued_at_returns_to_issued(self):
        from datetime import date
        self.invoice.issued_at = date.today()
        self.invoice.save(update_fields=["issued_at", "updated_at"])
        p = make_payment(self.invoice, Decimal("500.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        p.delete()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)

    def test_deleting_payment_from_partially_paid_invoice_with_issued_at_returns_to_issued(self):
        from datetime import date
        self.invoice.issued_at = date.today()
        self.invoice.save(update_fields=["issued_at", "updated_at"])
        p = make_payment(self.invoice, Decimal("250.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)
        p.delete()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)

    def test_sync_payment_status_does_not_touch_void_invoice(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])
        # Directly call sync — should be a no-op.
        self.invoice.sync_payment_status()
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.VOID)
