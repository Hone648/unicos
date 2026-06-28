from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from billing.models import Invoice, InvoiceLineItem, Payment
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


def make_line_item(
    invoice,
    description="Labor",
    quantity=Decimal("1.00"),
    unit_price=Decimal("100.00"),
    **kwargs,
):
    defaults = {
        "item_type": InvoiceLineItem.ItemType.LABOR,
        "description": description,
        "quantity": quantity,
        "unit_price": unit_price,
    }
    defaults.update(kwargs)
    return InvoiceLineItem.objects.create(invoice=invoice, **defaults)


def invoice_create_url(repair_order_pk):
    return reverse("billing:invoice_create", kwargs={"repair_order_pk": repair_order_pk})


def invoice_edit_url(pk):
    return reverse("billing:invoice_edit", kwargs={"pk": pk})


def payment_create_url(invoice_pk):
    return reverse("billing:payment_create", kwargs={"invoice_pk": invoice_pk})


def invoice_detail_url(pk):
    return reverse("billing:invoice_detail", kwargs={"pk": pk})


def line_item_create_url(invoice_pk):
    return reverse("billing:line_item_create", kwargs={"invoice_pk": invoice_pk})


def line_item_edit_url(pk):
    return reverse("billing:line_item_edit", kwargs={"pk": pk})


def invoice_issue_url(pk):
    return reverse("billing:invoice_issue", kwargs={"pk": pk})


def invoice_void_url(pk):
    return reverse("billing:invoice_void", kwargs={"pk": pk})


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

    def test_form_does_not_expose_invoice_number_field(self):
        response = self.client.get(invoice_create_url(self.ro.pk))
        self.assertNotContains(response, 'name="invoice_number"')

    def test_valid_post_creates_invoice_for_repair_order(self):
        self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        self.assertTrue(Invoice.objects.filter(repair_order=self.ro).exists())
        inv = Invoice.objects.get(repair_order=self.ro)
        self.assertEqual(inv.repair_order, self.ro)

    def test_valid_post_auto_generates_invoice_number(self):
        self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        inv = Invoice.objects.get(repair_order=self.ro)
        self.assertRegex(inv.invoice_number, r"^INV-\d{4}-\d{6}$")

    def test_valid_post_redirects_to_repair_order_detail(self):
        response = self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        self.assertRedirects(response, ro_detail_url(self.ro.pk))

    def test_valid_post_sets_created_by(self):
        self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        inv = Invoice.objects.get(repair_order=self.ro)
        self.assertEqual(inv.created_by, self.user)

    def test_valid_post_sets_updated_by(self):
        self.client.post(invoice_create_url(self.ro.pk), self._valid_data())
        inv = Invoice.objects.get(repair_order=self.ro)
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

    def test_edit_form_does_not_expose_editable_invoice_number(self):
        response = self.client.get(invoice_edit_url(self.invoice.pk))
        self.assertNotContains(response, 'name="invoice_number"')

    def test_edit_preserves_existing_invoice_number(self):
        original_number = self.invoice.invoice_number
        self.client.post(invoice_edit_url(self.invoice.pk), self._valid_data())
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.invoice_number, original_number)


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
        self.assertRedirects(response, ro_detail_url(self.ro.pk))
        self.assertFalse(Payment.objects.filter(invoice=self.invoice).exists())

    def test_get_for_void_invoice_redirects_to_ro_detail(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])
        response = self.client.get(payment_create_url(self.invoice.pk))
        self.assertRedirects(response, ro_detail_url(self.ro.pk))


# ---------------------------------------------------------------------------
# Invoice line item create
# ---------------------------------------------------------------------------

class LineItemCreateAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.invoice = make_invoice(self.ro)

    def test_login_required(self):
        url = line_item_create_url(self.invoice.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class LineItemCreateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-LI-CREATE")
        self.invoice = make_invoice(
            self.ro,
            number="INV-LI-CREATE",
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("10.00"),
        )

    def _valid_data(self, **overrides):
        data = {
            "item_type": InvoiceLineItem.ItemType.LABOR,
            "description": "Refinish labor",
            "quantity": "2.00",
            "unit_price": "75.00",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        response = self.client.get(line_item_create_url(self.invoice.pk))
        self.assertEqual(response.status_code, 200)

    def test_form_does_not_expose_invoice(self):
        response = self.client.get(line_item_create_url(self.invoice.pk))
        self.assertNotContains(response, 'name="invoice"')

    def test_valid_post_creates_line_item(self):
        self.client.post(line_item_create_url(self.invoice.pk), self._valid_data())
        self.assertEqual(InvoiceLineItem.objects.filter(invoice=self.invoice).count(), 1)

    def test_valid_post_redirects_to_repair_order_detail(self):
        response = self.client.post(line_item_create_url(self.invoice.pk), self._valid_data())
        self.assertRedirects(response, ro_detail_url(self.ro.pk))

    def test_valid_post_recalculates_invoice_subtotal(self):
        self.client.post(line_item_create_url(self.invoice.pk), self._valid_data())
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.subtotal, Decimal("150.00"))
        self.assertEqual(self.invoice.total_amount, Decimal("160.00"))

    def test_line_item_is_tied_to_invoice_from_url(self):
        self.client.post(line_item_create_url(self.invoice.pk), self._valid_data())
        line_item = InvoiceLineItem.objects.get()
        self.assertEqual(line_item.invoice, self.invoice)

    def test_invalid_post_re_renders_form_with_errors(self):
        response = self.client.post(
            line_item_create_url(self.invoice.pk),
            self._valid_data(quantity="0.00"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ensure this value is greater than or equal to 0.01")
        self.assertFalse(InvoiceLineItem.objects.filter(invoice=self.invoice).exists())


# ---------------------------------------------------------------------------
# Invoice line item edit
# ---------------------------------------------------------------------------

class LineItemEditAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.invoice = make_invoice(self.ro, subtotal=Decimal("0.00"), tax_amount=Decimal("0.00"))
        self.line_item = make_line_item(self.invoice)

    def test_login_required(self):
        url = line_item_edit_url(self.line_item.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class LineItemEditTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-LI-EDIT")
        self.invoice = make_invoice(
            self.ro,
            number="INV-LI-EDIT",
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
        )
        self.line_item = make_line_item(
            self.invoice,
            description="Original labor",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
        )

    def _valid_data(self, **overrides):
        data = {
            "item_type": InvoiceLineItem.ItemType.PARTS,
            "description": "Updated part",
            "quantity": "3.00",
            "unit_price": "50.00",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        response = self.client.get(line_item_edit_url(self.line_item.pk))
        self.assertEqual(response.status_code, 200)

    def test_form_shows_existing_values(self):
        response = self.client.get(line_item_edit_url(self.line_item.pk))
        self.assertContains(response, "Original labor")
        self.assertContains(response, "100.00")

    def test_form_does_not_expose_invoice(self):
        response = self.client.get(line_item_edit_url(self.line_item.pk))
        self.assertNotContains(response, 'name="invoice"')

    def test_valid_post_updates_line_item(self):
        self.client.post(line_item_edit_url(self.line_item.pk), self._valid_data())
        self.line_item.refresh_from_db()
        self.assertEqual(self.line_item.description, "Updated part")
        self.assertEqual(self.line_item.item_type, InvoiceLineItem.ItemType.PARTS)

    def test_valid_post_redirects_to_repair_order_detail(self):
        response = self.client.post(line_item_edit_url(self.line_item.pk), self._valid_data())
        self.assertRedirects(response, ro_detail_url(self.ro.pk))

    def test_valid_post_recalculates_invoice_subtotal(self):
        self.client.post(line_item_edit_url(self.line_item.pk), self._valid_data())
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.subtotal, Decimal("150.00"))

    def test_edit_preserves_invoice(self):
        self.client.post(line_item_edit_url(self.line_item.pk), self._valid_data())
        self.line_item.refresh_from_db()
        self.assertEqual(self.line_item.invoice, self.invoice)

    def test_invalid_edit_that_would_make_total_less_than_paid_is_rejected(self):
        make_payment(self.invoice, Decimal("90.00"))
        response = self.client.post(
            line_item_edit_url(self.line_item.pk),
            self._valid_data(quantity="1.00", unit_price="50.00"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Line item changes cannot make the invoice total less than the amount already paid.",
        )
        self.line_item.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(self.line_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.invoice.subtotal, Decimal("100.00"))


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

    def test_detail_with_invoice_shows_add_line_item_link(self):
        invoice = make_invoice(self.ro, number="INV-BILL-LI")
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, line_item_create_url(invoice.pk))

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

    def test_detail_with_line_items_shows_line_item_rows(self):
        invoice = make_invoice(
            self.ro,
            number="INV-BILL-05",
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("25.00"),
        )
        make_line_item(
            invoice,
            description="Bumper cover",
            quantity=Decimal("1.00"),
            unit_price=Decimal("250.00"),
            item_type=InvoiceLineItem.ItemType.PARTS,
        )
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, "Bumper cover")
        self.assertContains(response, "Parts")
        self.assertContains(response, "250.00")

    def test_detail_with_line_items_shows_edit_line_item_link(self):
        invoice = make_invoice(self.ro, number="INV-BILL-06", subtotal=Decimal("0.00"))
        line_item = make_line_item(invoice)
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, line_item_edit_url(line_item.pk))

    def test_detail_subtotal_reflects_line_item_subtotal(self):
        invoice = make_invoice(
            self.ro,
            number="INV-BILL-07",
            subtotal=Decimal("0.00"),
            tax_amount=Decimal("10.00"),
        )
        make_line_item(
            invoice,
            quantity=Decimal("2.00"),
            unit_price=Decimal("80.00"),
        )
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, "160.00")
        self.assertContains(response, "170.00")

    def test_detail_without_invoice_does_not_show_edit_or_payment_links(self):
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertNotContains(response, "Edit Invoice")
        self.assertNotContains(response, "Record Payment")


# ---------------------------------------------------------------------------
# Invoice detail / print view
# ---------------------------------------------------------------------------

class InvoiceDetailAuthTests(TestCase):
    def setUp(self):
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle, number="RO-AUTH-DET")
        self.invoice = make_invoice(ro, number="INV-AUTH-DET")

    def test_login_required(self):
        url = invoice_detail_url(self.invoice.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class InvoiceDetailDisplayTests(TestCase):
    def setUp(self):
        self.user = make_user(username="det_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-DET-INV")
        self.invoice = make_invoice(
            self.ro,
            number="INV-DET-01",
            subtotal=Decimal("400.00"),
            tax_amount=Decimal("40.00"),
        )

    def test_get_returns_200(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertEqual(response.status_code, 200)

    def test_page_shows_invoice_number(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "INV-DET-01")

    def test_page_shows_repair_order_number(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "RO-DET-INV")

    def test_page_shows_customer(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "Jane")  # customer first name

    def test_page_shows_vehicle(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "Honda")  # vehicle make

    def test_page_shows_status(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, self.invoice.get_status_display())

    def test_page_shows_subtotal(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "400.00")

    def test_page_shows_tax(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "40.00")

    def test_page_shows_total(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "440.00")

    def test_page_shows_paid(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "0.00")  # no payments yet

    def test_page_shows_balance_due(self):
        make_payment(self.invoice, Decimal("100.00"))
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "340.00")  # 440 - 100

    def test_page_shows_line_item_rows_when_present(self):
        make_line_item(self.invoice, description="Paint labor")
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "Paint labor")

    def test_page_shows_no_line_items_message_when_none(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "No line items on this invoice.")

    def test_page_shows_payment_rows_when_present(self):
        make_payment(self.invoice, Decimal("75.00"))
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "75.00")

    def test_page_shows_no_payments_message_when_none(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "No payments recorded.")


class InvoiceDetailActionTests(TestCase):
    def setUp(self):
        self.user = make_user(username="act_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-ACT-INV")
        self.invoice = make_invoice(
            self.ro,
            number="INV-ACT-01",
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("20.00"),
        )

    def test_page_links_back_to_repair_order(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, ro_detail_url(self.ro.pk))

    def test_page_links_to_edit_invoice(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, invoice_edit_url(self.invoice.pk))

    def test_page_links_to_add_line_item(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, line_item_create_url(self.invoice.pk))

    def test_page_shows_record_payment_when_balance_remains(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, payment_create_url(self.invoice.pk))

    def test_page_hides_record_payment_when_fully_paid(self):
        make_payment(self.invoice, Decimal("220.00"))
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertNotContains(response, payment_create_url(self.invoice.pk))

    def test_page_hides_record_payment_when_void(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertNotContains(response, payment_create_url(self.invoice.pk))


class RepairOrderDetailViewPrintLinkTests(TestCase):
    def setUp(self):
        self.user = make_user(username="vp_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin="3VWFE21C04M000001")
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-VP-01")

    def test_invoice_summary_shows_view_print_link_when_invoice_exists(self):
        invoice = make_invoice(self.ro, number="INV-VP-01")
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, invoice_detail_url(invoice.pk))

    def test_invoice_summary_does_not_show_view_print_link_when_no_invoice(self):
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertNotContains(response, "View/Print Invoice")


class InvoiceDetailScopeTests(TestCase):
    def setUp(self):
        self.user = make_user(username="scope_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-SCOPE-INV")
        self.invoice = make_invoice(self.ro, number="INV-SCOPE-01")

    def test_invoice_detail_does_not_expose_mutation_form_fields(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertNotContains(response, 'name="invoice_number"')
        self.assertNotContains(response, 'name="subtotal"')
        self.assertNotContains(response, 'name="status"')

    def test_invoice_detail_post_is_safe_and_read_only(self):
        response = self.client.post(invoice_detail_url(self.invoice.pk))
        self.assertEqual(response.status_code, 200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.invoice_number, "INV-SCOPE-01")


# ---------------------------------------------------------------------------
# Invoice issue action
# ---------------------------------------------------------------------------

class InvoiceIssueAuthTests(TestCase):
    def setUp(self):
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle, number="RO-ISS-AUTH")
        self.invoice = make_invoice(ro, number="INV-ISS-AUTH")

    def test_login_required(self):
        url = invoice_issue_url(self.invoice.pk)
        response = self.client.post(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class InvoiceIssueTests(TestCase):
    def setUp(self):
        self.user = make_user(username="iss_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-ISS-01")
        self.invoice = make_invoice(self.ro, number="INV-ISS-01")

    def test_get_redirects_to_invoice_detail(self):
        response = self.client.get(invoice_issue_url(self.invoice.pk))
        self.assertRedirects(response, invoice_detail_url(self.invoice.pk))

    def test_post_draft_sets_status_to_issued(self):
        self.client.post(invoice_issue_url(self.invoice.pk))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)

    def test_post_draft_sets_issued_at_when_blank(self):
        self.assertIsNone(self.invoice.issued_at)
        self.client.post(invoice_issue_url(self.invoice.pk))
        self.invoice.refresh_from_db()
        self.assertIsNotNone(self.invoice.issued_at)

    def test_post_draft_preserves_issued_at_when_set(self):
        original_date = date(2025, 3, 15)
        self.invoice.issued_at = original_date
        self.invoice.save(update_fields=["issued_at", "updated_at"])
        self.client.post(invoice_issue_url(self.invoice.pk))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.issued_at, original_date)

    def test_post_draft_sets_updated_by(self):
        self.client.post(invoice_issue_url(self.invoice.pk))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.updated_by, self.user)

    def test_post_draft_redirects_to_ro_detail(self):
        response = self.client.post(invoice_issue_url(self.invoice.pk))
        self.assertRedirects(response, ro_detail_url(self.ro.pk))

    def test_post_non_draft_does_not_change_status(self):
        self.invoice.status = Invoice.Status.ISSUED
        self.invoice.save(update_fields=["status", "updated_at"])
        self.client.post(invoice_issue_url(self.invoice.pk))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)

    def test_post_non_draft_redirects_to_ro_detail(self):
        self.invoice.status = Invoice.Status.ISSUED
        self.invoice.save(update_fields=["status", "updated_at"])
        response = self.client.post(invoice_issue_url(self.invoice.pk))
        self.assertRedirects(response, ro_detail_url(self.ro.pk))


# ---------------------------------------------------------------------------
# Invoice void action
# ---------------------------------------------------------------------------

class InvoiceVoidAuthTests(TestCase):
    def setUp(self):
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle, number="RO-VOID-AUTH")
        self.invoice = make_invoice(ro, number="INV-VOID-AUTH")

    def test_login_required(self):
        url = invoice_void_url(self.invoice.pk)
        response = self.client.post(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class InvoiceVoidTests(TestCase):
    def setUp(self):
        self.user = make_user(username="void_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-VOID-01")
        self.invoice = make_invoice(self.ro, number="INV-VOID-01")

    def test_get_redirects_to_invoice_detail(self):
        response = self.client.get(invoice_void_url(self.invoice.pk))
        self.assertRedirects(response, invoice_detail_url(self.invoice.pk))

    def test_post_sets_status_to_void(self):
        self.client.post(invoice_void_url(self.invoice.pk))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.VOID)

    def test_post_sets_updated_by(self):
        self.client.post(invoice_void_url(self.invoice.pk))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.updated_by, self.user)

    def test_post_redirects_to_ro_detail(self):
        response = self.client.post(invoice_void_url(self.invoice.pk))
        self.assertRedirects(response, ro_detail_url(self.ro.pk))

    def test_post_already_void_is_non_destructive(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])
        self.client.post(invoice_void_url(self.invoice.pk))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.VOID)

    def test_void_invoice_still_visible_on_ro_detail(self):
        self.client.post(invoice_void_url(self.invoice.pk))
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INV-VOID-01")

    def test_void_invoice_detail_still_loads(self):
        self.client.post(invoice_void_url(self.invoice.pk))
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "INV-VOID-01")

    def test_void_paid_invoice_does_not_revive_payment_status(self):
        make_payment(self.invoice, Decimal("500.00"))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)
        self.client.post(invoice_void_url(self.invoice.pk))
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.VOID)


# ---------------------------------------------------------------------------
# Invoice lifecycle UI rendering
# ---------------------------------------------------------------------------

class InvoiceLifecycleUITests(TestCase):
    def setUp(self):
        self.user = make_user(username="ui_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin="4T1BF3EK8AU155890")
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-UI-LC-01")
        self.invoice = make_invoice(
            self.ro,
            number="INV-UI-LC-01",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("10.00"),
        )

    def _issue(self):
        self.invoice.status = Invoice.Status.ISSUED
        self.invoice.save(update_fields=["status", "updated_at"])

    def _void(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])

    # --- invoice detail ---

    def test_draft_invoice_detail_shows_issue_button(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "Issue Invoice")

    def test_issued_invoice_detail_does_not_show_issue_button(self):
        self._issue()
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertNotContains(response, "Issue Invoice")

    def test_non_void_invoice_detail_shows_void_button(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, "Void Invoice")

    def test_void_invoice_detail_does_not_show_void_button(self):
        self._void()
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertNotContains(response, "Void Invoice")

    def test_void_invoice_detail_does_not_show_record_payment(self):
        self._void()
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertNotContains(response, payment_create_url(self.invoice.pk))

    def test_invoice_detail_issue_form_posts_to_correct_url(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, invoice_issue_url(self.invoice.pk))

    def test_invoice_detail_void_form_posts_to_correct_url(self):
        response = self.client.get(invoice_detail_url(self.invoice.pk))
        self.assertContains(response, invoice_void_url(self.invoice.pk))

    # --- repair-order invoice summary ---

    def test_draft_ro_summary_shows_issue_button(self):
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, "Issue Invoice")

    def test_issued_ro_summary_does_not_show_issue_button(self):
        self._issue()
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertNotContains(response, "Issue Invoice")

    def test_non_void_ro_summary_shows_void_button(self):
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, "Void Invoice")

    def test_void_ro_summary_does_not_show_void_button(self):
        self._void()
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertNotContains(response, "Void Invoice")

    def test_void_ro_summary_hides_record_payment(self):
        self._void()
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertNotContains(response, payment_create_url(self.invoice.pk))
