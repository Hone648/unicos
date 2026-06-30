from datetime import date
from decimal import Decimal

from billing.admin import (
    InvoiceAdmin,
    InvoiceLineItemAdmin,
    InvoiceLineItemInline,
    PaymentAdmin,
    PaymentInline,
)
from billing.models import Invoice, InvoiceLineItem, Payment
from customers.models import Customer
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
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


def make_superuser(username="root"):
    return get_user_model().objects.create_superuser(
        username=username, password="pw-test-12345", email="root@example.com"
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
    return Invoice.objects.create(repair_order=repair_order, invoice_number=number, **defaults)


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

    def test_invoice_admin_includes_line_item_inline(self):
        self.assertIn(InvoiceLineItemInline, self.admin_instance.inlines)

    def test_invoice_admin_exposes_source_estimate(self):
        self.assertIn("source_estimate", self.admin_instance.raw_id_fields)
        self.assertIn("source_estimate", self.admin_instance.list_select_related)


class InvoiceAdminDisplayMethodTests(TestCase):
    def setUp(self):
        self.admin_instance = InvoiceAdmin(Invoice, admin.site)
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle)
        self.invoice = make_invoice(ro, subtotal=Decimal("400.00"), tax_amount=Decimal("40.00"))

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
# InvoiceLineItemAdmin tests
# ---------------------------------------------------------------------------


class InvoiceLineItemAdminTests(TestCase):
    def setUp(self):
        self.admin_instance = InvoiceLineItemAdmin(InvoiceLineItem, admin.site)
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle)
        self.invoice = make_invoice(ro, subtotal=Decimal("0.00"), tax_amount=Decimal("0.00"))
        self.line_item = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            item_type=InvoiceLineItem.ItemType.PARTS,
            description="Bumper cover",
            quantity=Decimal("1.00"),
            unit_price=Decimal("250.00"),
        )

    def test_line_item_admin_is_registered(self):
        self.assertIs(admin.site._registry[InvoiceLineItem].__class__, InvoiceLineItemAdmin)

    def test_line_total_display(self):
        self.assertEqual(
            self.admin_instance.line_total_display(self.line_item),
            Decimal("250.00"),
        )

    def test_line_item_admin_disables_delete(self):
        request = make_request(make_user())
        self.assertFalse(self.admin_instance.has_delete_permission(request, self.line_item))


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


# ---------------------------------------------------------------------------
# Slice 43: admin service-alignment tests
# ---------------------------------------------------------------------------


class InvoiceAdminFieldProtectionTests(TestCase):
    def setUp(self):
        self.admin_instance = InvoiceAdmin(Invoice, admin.site)
        customer = make_customer()
        vehicle = make_vehicle(customer)
        self.ro = make_repair_order(customer, vehicle)
        self.request = make_request(make_user())

    def test_status_is_readonly(self):
        self.assertIn("status", self.admin_instance.readonly_fields)

    def test_subtotal_editable_without_line_items(self):
        invoice = make_invoice(self.ro, number="INV-NOITEMS")
        readonly = self.admin_instance.get_readonly_fields(self.request, invoice)
        self.assertNotIn("subtotal", readonly)

    def test_subtotal_readonly_with_line_items(self):
        invoice = make_invoice(self.ro, number="INV-ITEMS", subtotal=Decimal("0.00"))
        InvoiceLineItem.objects.create(
            invoice=invoice,
            item_type=InvoiceLineItem.ItemType.LABOR,
            description="Paint",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
        )
        readonly = self.admin_instance.get_readonly_fields(self.request, invoice)
        self.assertIn("subtotal", readonly)

    def test_subtotal_editable_on_add(self):
        readonly = self.admin_instance.get_readonly_fields(self.request, None)
        self.assertNotIn("subtotal", readonly)


class InvoiceAdminLifecycleActionTests(TestCase):
    def setUp(self):
        self.admin_instance = InvoiceAdmin(Invoice, admin.site)
        self.user = make_user(username="admin-lifecycle")
        self.request = make_request(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_issue_selected_invoices_issues_draft_invoice(self):
        invoice = make_invoice(self.ro, number="INV-ISSUE")
        queryset = Invoice.objects.filter(pk=invoice.pk)
        self.admin_instance.issue_selected_invoices(self.request, queryset)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)
        self.assertIsNotNone(invoice.issued_at)
        self.assertEqual(invoice.updated_by, self.user)

    def test_void_selected_invoices_voids_invoice(self):
        invoice = make_invoice(self.ro, number="INV-VOID")
        queryset = Invoice.objects.filter(pk=invoice.pk)
        self.admin_instance.void_selected_invoices(self.request, queryset)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.VOID)
        self.assertEqual(invoice.updated_by, self.user)

    def test_issue_blocked_for_final_repair_order(self):
        invoice = make_invoice(self.ro, number="INV-ISSUE-FINAL")
        RepairOrder.objects.filter(pk=self.ro.pk).update(status=RepairOrder.Status.CLOSED)
        queryset = Invoice.objects.filter(pk=invoice.pk)
        self.admin_instance.issue_selected_invoices(self.request, queryset)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)

    def test_void_blocked_for_final_repair_order(self):
        invoice = make_invoice(self.ro, number="INV-VOID-FINAL")
        RepairOrder.objects.filter(pk=self.ro.pk).update(status=RepairOrder.Status.CLOSED)
        queryset = Invoice.objects.filter(pk=invoice.pk)
        self.admin_instance.void_selected_invoices(self.request, queryset)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)


class InvoiceLineItemInlinePermissionTests(TestCase):
    def test_inline_disallows_add_change_delete(self):
        inline = InvoiceLineItemInline(Invoice, admin.site)
        request = make_request(make_user())
        self.assertFalse(inline.has_add_permission(request))
        self.assertFalse(inline.has_change_permission(request))
        self.assertFalse(inline.has_delete_permission(request))


class PaymentInlinePermissionTests(TestCase):
    def test_inline_disallows_add_change_delete(self):
        inline = PaymentInline(Invoice, admin.site)
        request = make_request(make_user())
        self.assertFalse(inline.has_add_permission(request))
        self.assertFalse(inline.has_change_permission(request))
        self.assertFalse(inline.has_delete_permission(request))


class InvoiceLineItemAdminServiceRoutingTests(TestCase):
    def setUp(self):
        self.admin_instance = InvoiceLineItemAdmin(InvoiceLineItem, admin.site)
        self.user = make_user(username="li-admin")
        self.request = make_request(self.user)
        customer = make_customer()
        vehicle = make_vehicle(customer)
        self.ro = make_repair_order(customer, vehicle)

    def test_save_model_create_routes_through_service(self):
        invoice = make_invoice(self.ro, number="INV-LI-CREATE", subtotal=Decimal("0.00"))
        item = InvoiceLineItem(
            invoice=invoice,
            item_type=InvoiceLineItem.ItemType.PARTS,
            description="Bumper cover",
            quantity=Decimal("1.00"),
            unit_price=Decimal("250.00"),
        )
        self.admin_instance.save_model(self.request, item, None, change=False)
        self.assertIsNotNone(item.pk)
        self.assertTrue(InvoiceLineItem.objects.filter(pk=item.pk).exists())
        invoice.refresh_from_db()
        self.assertEqual(invoice.subtotal, Decimal("250.00"))

    def test_save_model_edit_routes_through_service(self):
        invoice = make_invoice(self.ro, number="INV-LI-EDIT", subtotal=Decimal("0.00"))
        item = InvoiceLineItem.objects.create(
            invoice=invoice,
            item_type=InvoiceLineItem.ItemType.PARTS,
            description="Bumper cover",
            quantity=Decimal("1.00"),
            unit_price=Decimal("250.00"),
        )
        item.description = "Front bumper cover"
        self.admin_instance.save_model(self.request, item, None, change=True)
        item.refresh_from_db()
        self.assertEqual(item.description, "Front bumper cover")

    def test_save_model_blocked_for_void_invoice(self):
        invoice = make_invoice(self.ro, number="INV-LI-VOID", subtotal=Decimal("0.00"))
        Invoice.objects.filter(pk=invoice.pk).update(status=Invoice.Status.VOID)
        invoice.refresh_from_db()
        item = InvoiceLineItem(
            invoice=invoice,
            item_type=InvoiceLineItem.ItemType.PARTS,
            description="Bumper cover",
            quantity=Decimal("1.00"),
            unit_price=Decimal("250.00"),
        )
        self.admin_instance.save_model(self.request, item, None, change=False)
        self.assertIsNone(item.pk)
        self.assertEqual(InvoiceLineItem.objects.filter(invoice=invoice).count(), 0)

    def test_save_model_blocked_for_final_repair_order(self):
        invoice = make_invoice(self.ro, number="INV-LI-FINAL", subtotal=Decimal("0.00"))
        RepairOrder.objects.filter(pk=self.ro.pk).update(status=RepairOrder.Status.CLOSED)
        invoice.refresh_from_db()
        item = InvoiceLineItem(
            invoice=invoice,
            item_type=InvoiceLineItem.ItemType.PARTS,
            description="Bumper cover",
            quantity=Decimal("1.00"),
            unit_price=Decimal("250.00"),
        )
        self.admin_instance.save_model(self.request, item, None, change=False)
        self.assertIsNone(item.pk)
        self.assertEqual(InvoiceLineItem.objects.filter(invoice=invoice).count(), 0)


class PaymentAdminPermissionTests(TestCase):
    def setUp(self):
        self.admin_instance = PaymentAdmin(Payment, admin.site)
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle)
        self.invoice = make_invoice(ro, number="INV-PAY-PERM")
        self.request = make_request(make_user())

    def test_has_change_permission_false_for_existing_payment(self):
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("100.00"),
            method=Payment.Method.CASH,
            payment_date=date.today(),
        )
        self.assertFalse(self.admin_instance.has_change_permission(self.request, payment))

    def test_has_change_permission_true_for_add_view(self):
        request = make_request(make_superuser())
        self.assertTrue(self.admin_instance.has_change_permission(request, None))

    def test_has_delete_permission_false(self):
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("100.00"),
            method=Payment.Method.CASH,
            payment_date=date.today(),
        )
        self.assertFalse(self.admin_instance.has_delete_permission(self.request, payment))


class PaymentAdminServiceRoutingTests(TestCase):
    def setUp(self):
        self.admin_instance = PaymentAdmin(Payment, admin.site)
        self.user = make_user(username="pay-admin")
        self.request = make_request(self.user)
        customer = make_customer()
        vehicle = make_vehicle(customer)
        self.ro = make_repair_order(customer, vehicle)

    def test_save_model_create_routes_through_service(self):
        invoice = make_invoice(self.ro, number="INV-PAY-CREATE")
        payment = Payment(
            invoice=invoice,
            amount=Decimal("100.00"),
            method=Payment.Method.CASH,
            payment_date=date.today(),
        )
        self.admin_instance.save_model(self.request, payment, None, change=False)
        self.assertIsNotNone(payment.pk)
        self.assertEqual(payment.received_by, self.user)
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, Decimal("100.00"))

    def test_save_model_blocked_for_void_invoice(self):
        invoice = make_invoice(self.ro, number="INV-PAY-VOID")
        Invoice.objects.filter(pk=invoice.pk).update(status=Invoice.Status.VOID)
        invoice.refresh_from_db()
        payment = Payment(
            invoice=invoice,
            amount=Decimal("100.00"),
            method=Payment.Method.CASH,
            payment_date=date.today(),
        )
        self.admin_instance.save_model(self.request, payment, None, change=False)
        self.assertIsNone(payment.pk)
        self.assertEqual(Payment.objects.filter(invoice=invoice).count(), 0)

    def test_save_model_noop_for_existing_payment(self):
        invoice = make_invoice(self.ro, number="INV-PAY-NOOP")
        payment = Payment.objects.create(
            invoice=invoice,
            amount=Decimal("100.00"),
            method=Payment.Method.CASH,
            payment_date=date.today(),
        )
        payment.amount = Decimal("999.00")
        self.admin_instance.save_model(self.request, payment, None, change=True)
        payment.refresh_from_db()
        self.assertEqual(payment.amount, Decimal("100.00"))
