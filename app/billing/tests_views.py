from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from billing.models import Invoice, Payment
from customers.models import Customer
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username="staffer", **kwargs):
    return get_user_model().objects.create_user(
        username=username, password="pw-test-12345", **kwargs
    )


def make_customer(**kwargs):
    defaults = {
        "customer_type": Customer.CustomerType.INDIVIDUAL,
        "first_name": "Jane",
        "last_name": "Smith",
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
    defaults = {"payment_date": date.today(), "method": Payment.Method.CASH}
    defaults.update(kwargs)
    return Payment.objects.create(invoice=invoice, amount=amount, **defaults)


def invoice_create_url(repair_order_pk):
    return reverse("billing:invoice_create", kwargs={"repair_order_pk": repair_order_pk})


def invoice_edit_url(pk):
    return reverse("billing:invoice_edit", kwargs={"pk": pk})


def payment_create_url(invoice_pk):
    return reverse("billing:payment_create", kwargs={"invoice_pk": invoice_pk})


def ro_detail_url(pk):
    return reverse("repair_orders:detail", kwargs={"pk": pk})


# ---------------------------------------------------------------------------
# Invoice create
# ---------------------------------------------------------------------------

class InvoiceCreateAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_login_required(self):
        url = invoice_create_url(self.ro.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class InvoiceCreateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-INV-01")

    def _valid_data(self, **overrides):
        data = {
            "invoice_number": "INV-CREATE-01",
            "issued_at": "",
            "due_date": "",
            "subtotal": "500.00",
            "tax_amount": "50.00",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        response = self.client.get(invoice_create_url(self.ro.pk))
        self.assertEqual(response.status_code, 200)

    def test_form_does_not_expose_repair_order_field(self):
        response = self.client.get(invoice_create_url(self.ro.pk))
        self.assertNotContains(response, 'name="repair_order"')

    def test_form_does_not_expose_status_field(self):
        response = self.client.get(invoice_create_url(self.ro.pk))
        self.assertNotContains(response, 'name="status"')

    def test_valid_post_creates_invoice_for_repair_order(self):
        self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        self.assertTrue(Invoice.objects.filter(invoice_number="INV-CREATE-01").exists())
        inv = Invoice.objects.get(invoice_number="INV-CREATE-01")
        self.assertEqual(inv.repair_order, self.ro)

    def test_valid_post_redirects_to_repair_order_detail(self):
        response = self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        self.assertRedirects(response, ro_detail_url(self.ro.pk))

    def test_valid_post_sets_created_by(self):
        self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        inv = Invoice.objects.get(invoice_number="INV-CREATE-01")
        self.assertEqual(inv.created_by, self.user)

    def test_valid_post_sets_updated_by(self):
        self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        inv = Invoice.objects.get(invoice_number="INV-CREATE-01")
        self.assertEqual(inv.updated_by, self.user)

    def test_duplicate_invoice_does_not_create_second_invoice(self):
        make_invoice(self.ro, number="INV-EXISTING")
        self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        self.assertEqual(Invoice.objects.filter(repair_order=self.ro).count(), 1)

    def test_duplicate_invoice_redirects_to_repair_order_detail(self):
        make_invoice(self.ro, number="INV-EXISTING")
        response = self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        self.assertRedirects(response, ro_detail_url(self.ro.pk))


# ---------------------------------------------------------------------------
# Invoice edit
# ---------------------------------------------------------------------------

class InvoiceEditAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.invoice = make_invoice(self.ro)

    def test_login_required(self):
        url = invoice_edit_url(self.invoice.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class InvoiceEditTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-EDIT-INV")
        self.invoice = make_invoice(
            self.ro,
            number="INV-EDIT-01",
            subtotal=Decimal("300.00"),
            tax_amount=Decimal("30.00"),
        )

    def _valid_data(self, **overrides):
        data = {
            "invoice_number": self.invoice.invoice_number,
            "issued_at": "",
            "due_date": "",
            "subtotal": "300.00",
            "tax_amount": "30.00",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        response = self.client.get(invoice_edit_url(self.invoice.pk))
        self.assertEqual(response.status_code, 200)

    def test_form_shows_existing_values(self):
        response = self.client.get(invoice_edit_url(self.invoice.pk))
        self.assertContains(response, "INV-EDIT-01")
        self.assertContains(response, "300.00")

    def test_form_does_not_expose_repair_order_field(self):
        response = self.client.get(invoice_edit_url(self.invoice.pk))
        self.assertNotContains(response, 'name="repair_order"')

    def test_form_does_not_expose_status_field(self):
        response = self.client.get(invoice_edit_url(self.invoice.pk))
        self.assertNotContains(response, 'name="status"')

    def test_valid_post_updates_editable_fields(self):
        self.client.post(
            invoice_edit_url(self.invoice.pk),
            self._valid_data(subtotal="400.00", notes="Updated note"),
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.subtotal, Decimal("400.00"))
        self.assertEqual(self.invoice.notes, "Updated note")

    def test_valid_post_redirects_to_repair_order_detail(self):
        response = self.client.post(invoice_edit_url(self.invoice.pk), self._valid_data())
        self.assertRedirects(response, ro_detail_url(self.ro.pk))

    def test_valid_post_sets_updated_by(self):
        self.client.post(invoice_edit_url(self.invoice.pk), self._valid_data())
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.updated_by, self.user)

    def test_valid_post_preserves_repair_order(self):
        self.client.post(invoice_edit_url(self.invoice.pk), self._valid_data())
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.repair_order, self.ro)

    def test_valid_post_does_not_change_status(self):
        original_status = self.invoice.status
        self.client.post(invoice_edit_url(self.invoice.pk), self._valid_data())
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, original_status)


# ---------------------------------------------------------------------------
# Payment create
# ---------------------------------------------------------------------------

class PaymentCreateAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.invoice = make_invoice(self.ro)

    def test_login_required(self):
        url = payment_create_url(self.invoice.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class PaymentCreateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-PAY-01")
        # Invoice total = 550.00
        self.invoice = make_invoice(
            self.ro,
            number="INV-PAY-01",
            subtotal=Decimal("500.00"),
            tax_amount=Decimal("50.00"),
        )

    def _valid_data(self, **overrides):
        data = {
            "payment_date": date.today().isoformat(),
            "amount": "100.00",
            "method": "cash",
            "reference": "",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        response = self.client.get(payment_create_url(self.invoice.pk))
        self.assertEqual(response.status_code, 200)

    def test_form_does_not_expose_invoice_field(self):
        response = self.client.get(payment_create_url(self.invoice.pk))
        self.assertNotContains(response, 'name="invoice"')

    def test_valid_post_creates_payment(self):
        self.client.post(payment_create_url(self.invoice.pk), self._valid_data())
        self.assertEqual(Payment.objects.filter(invoice=self.invoice).count(), 1)

    def test_valid_post_redirects_to_repair_order_detail(self):
        response = self.client.post(payment_create_url(self.invoice.pk), self._valid_data())
        self.assertRedirects(response, ro_detail_url(self.ro.pk))

    def test_valid_post_sets_received_by(self):
        self.client.post(payment_create_url(self.invoice.pk), self._valid_data())
        payment = Payment.objects.get(invoice=self.invoice)
        self.assertEqual(payment.received_by, self.user)

    def test_valid_post_links_payment_to_invoice_from_url(self):
        self.client.post(payment_create_url(self.invoice.pk), self._valid_data())
        payment = Payment.objects.get(invoice=self.invoice)
        self.assertEqual(payment.invoice, self.invoice)

    def test_partial_payment_sets_invoice_to_partially_paid(self):
        self.client.post(payment_create_url(self.invoice.pk), self._valid_data(amount="200.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)

    def test_full_payment_sets_invoice_to_paid(self):
        self.client.post(payment_create_url(self.invoice.pk), self._valid_data(amount="550.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

    def test_overpayment_is_rejected_and_does_not_create_payment(self):
        response = self.client.post(
            payment_create_url(self.invoice.pk), self._valid_data(amount="9999.00")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Payment.objects.filter(invoice=self.invoice).exists())

    def test_zero_amount_is_rejected(self):
        response = self.client.post(
            payment_create_url(self.invoice.pk), self._valid_data(amount="0.00")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Payment.objects.filter(invoice=self.invoice).exists())

    def test_payment_against_void_invoice_is_rejected(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])
        response = self.client.post(
            payment_create_url(self.invoice.pk), self._valid_data()
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Payment.objects.filter(invoice=self.invoice).exists())


# ---------------------------------------------------------------------------
# Repair-order detail billing display
# ---------------------------------------------------------------------------

class RepairOrderDetailBillingDisplayTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN_2)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-BILL-01")

    def test_detail_without_invoice_shows_create_invoice_link(self):
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, invoice_create_url(self.ro.pk))

    def test_detail_with_invoice_shows_edit_invoice_link(self):
        invoice = make_invoice(self.ro, number="INV-BILL-01")
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, invoice_edit_url(invoice.pk))

    def test_detail_with_invoice_and_balance_shows_record_payment_link(self):
        invoice = make_invoice(
            self.ro,
            number="INV-BILL-02",
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("0.00"),
        )
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, payment_create_url(invoice.pk))

    def test_detail_with_fully_paid_invoice_hides_record_payment_link(self):
        invoice = make_invoice(
            self.ro,
            number="INV-BILL-03",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("0.00"),
        )
        make_payment(invoice, Decimal("100.00"))
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertNotContains(response, payment_create_url(invoice.pk))

    def test_detail_with_payments_shows_payment_rows(self):
        invoice = make_invoice(
            self.ro,
            number="INV-BILL-04",
            subtotal=Decimal("300.00"),
            tax_amount=Decimal("0.00"),
        )
        make_payment(invoice, Decimal("150.00"))
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, "150.00")

    def test_detail_without_invoice_does_not_show_edit_or_payment_links(self):
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertNotContains(response, "Edit Invoice")
        self.assertNotContains(response, "Record Payment")
