from decimal import Decimal
from datetime import date

from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from billing.admin import InvoiceAdmin, PaymentAdmin
from billing.models import Invoice, Payment
from customers.models import Customer
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username="staffer", **kwargs):
    return get_user_model().objects.create_user(
        username=username, password="pw-test-12345", **kwargs
    )


def make_customer():
    return Customer.objects.create(
        customer_type=Customer.CustomerType.INDIVIDUAL,
        first_name="Test",
        last_name="Customer",
    )


def make_vehicle(customer):
    return Vehicle.objects.create(
        customer=customer, vin=VALID_VIN, make="Honda", model="Civic", year=2021
    )


def make_repair_order(customer, vehicle):
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number="RO-0001"
    )


def make_invoice(repair_order, number="INV-001", **kwargs):
    defaults = {"subtotal": Decimal("500.00"), "tax_amount": Decimal("50.00")}
    defaults.update(kwargs)
    return Invoice.objects.create(
        repair_order=repair_order, invoice_number=number, **defaults
    )


def make_request(user):
    factory = RequestFactory()
    request = factory.post("/")
    request.user = user
    setattr(request, "session", "session")
    setattr(request, "_messages", FallbackStorage(request))
    return request


# ---------------------------------------------------------------------------
# InvoiceAdmin tests
# ---------------------------------------------------------------------------

class InvoiceAdminSaveModelTests(TestCase):
    def setUp(self):
        self.admin_instance = InvoiceAdmin(Invoice, admin.site)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_save_model_sets_created_by_and_updated_by_on_new_invoice(self):
        user = make_user()
        request = make_request(user)
        inv = Invoice(
            repair_order=self.ro,
            invoice_number="INV-NEW",
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("20.00"),
        )
        self.admin_instance.save_model(request, inv, None, change=False)
        self.assertEqual(inv.created_by, user)
        self.assertEqual(inv.updated_by, user)

    def test_save_model_updates_updated_by_on_existing_invoice(self):
        creator = make_user(username="creator")
        inv = make_invoice(self.ro, created_by=creator)

        updater = make_user(username="updater")
        request = make_request(updater)
        self.admin_instance.save_model(request, inv, None, change=True)

        inv.refresh_from_db()
        self.assertEqual(inv.updated_by, updater)


class InvoiceAdminDisplayMethodTests(TestCase):
    def setUp(self):
        self.admin_instance = InvoiceAdmin(Invoice, admin.site)
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle)
        self.invoice = make_invoice(
            ro, subtotal=Decimal("400.00"), tax_amount=Decimal("40.00")
        )

    def test_total_amount_display(self):
        self.assertEqual(
            self.admin_instance.total_amount_display(self.invoice),
            Decimal("440.00"),
        )

    def test_amount_paid_display_with_no_payments(self):
        self.assertEqual(
            self.admin_instance.amount_paid_display(self.invoice),
            Decimal("0.00"),
        )

    def test_balance_due_display(self):
        self.assertEqual(
            self.admin_instance.balance_due_display(self.invoice),
            Decimal("440.00"),
        )

    def test_is_paid_display_false_when_unpaid(self):
        self.assertFalse(self.admin_instance.is_paid_display(self.invoice))

    def test_is_paid_display_true_when_paid(self):
        Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("440.00"),
            method=Payment.Method.CASH,
            payment_date=date.today(),
        )
        self.assertTrue(self.admin_instance.is_paid_display(self.invoice))


# ---------------------------------------------------------------------------
# PaymentAdmin tests
# ---------------------------------------------------------------------------

class PaymentAdminSaveModelTests(TestCase):
    def setUp(self):
        self.admin_instance = PaymentAdmin(Payment, admin.site)
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle)
        self.invoice = make_invoice(ro)

    def test_save_model_sets_received_by_when_missing(self):
        user = make_user()
        request = make_request(user)
        payment = Payment(
            invoice=self.invoice,
            amount=Decimal("100.00"),
            method=Payment.Method.CASH,
            payment_date=date.today(),
        )
        self.admin_instance.save_model(request, payment, None, change=False)
        self.assertEqual(payment.received_by, user)
