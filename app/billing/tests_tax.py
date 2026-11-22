"""Tax-totals tests for billing: invoice recalculation, payment/paid guards
including tax, detail rendering, and estimate-to-invoice tax preservation."""

from datetime import date
from decimal import Decimal

from accounts.authorization import ROLE_MANAGER
from billing.forms import InvoiceLineItemForm
from billing.models import Invoice, InvoiceLineItem, Payment
from billing.services import convert_estimate_to_invoice
from customers.models import Customer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from estimates.models import Estimate, EstimateLineItem
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


def make_user(username="tax-billing", role_name=ROLE_MANAGER):
    user = get_user_model().objects.create_user(username=username, password="pw-test-12345")
    if role_name:
        group, _ = Group.objects.get_or_create(name=role_name)
        user.groups.add(group)
    return user


def make_ro(number="RO-BTAX-001", vin=VALID_VIN):
    customer = Customer.objects.create(
        customer_type=Customer.CustomerType.INDIVIDUAL,
        first_name="Jane",
        last_name="Smith",
    )
    vehicle = Vehicle.objects.create(
        customer=customer, vin=vin, make="Honda", model="Civic", year=2021
    )
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number=number
    )


def make_invoice(ro, number="INV-BTAX-001", **kwargs):
    defaults = {"subtotal": Decimal("0.00"), "tax_amount": Decimal("0.00")}
    defaults.update(kwargs)
    return Invoice.objects.create(repair_order=ro, invoice_number=number, **defaults)


def make_line_item(invoice, **kwargs):
    defaults = {
        "item_type": InvoiceLineItem.ItemType.LABOR,
        "description": "Line",
        "quantity": Decimal("1.00"),
        "unit_price": Decimal("100.00"),
    }
    defaults.update(kwargs)
    return InvoiceLineItem.objects.create(invoice=invoice, **defaults)


class InvoiceTaxRecalculationTests(TestCase):
    def setUp(self):
        self.ro = make_ro()
        self.invoice = make_invoice(self.ro, tax_rate=Decimal("0.0825"))

    def test_recalculation_derives_taxable_subtotal_and_tax(self):
        make_line_item(
            self.invoice,
            item_type=InvoiceLineItem.ItemType.LABOR,
            unit_price=Decimal("300.00"),
            is_taxable=False,
        )
        make_line_item(
            self.invoice,
            item_type=InvoiceLineItem.ItemType.PARTS,
            unit_price=Decimal("200.00"),
            is_taxable=True,
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.subtotal, Decimal("500.00"))
        self.assertEqual(self.invoice.taxable_subtotal, Decimal("200.00"))
        self.assertEqual(self.invoice.tax_amount, Decimal("16.50"))
        self.assertEqual(self.invoice.total_amount, Decimal("516.50"))

    def test_total_amount_includes_calculated_tax(self):
        make_line_item(
            self.invoice,
            item_type=InvoiceLineItem.ItemType.PARTS,
            unit_price=Decimal("100.00"),
            is_taxable=True,
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.total_amount, Decimal("108.25"))

    def test_payment_cannot_exceed_total_including_tax(self):
        make_line_item(
            self.invoice,
            item_type=InvoiceLineItem.ItemType.PARTS,
            unit_price=Decimal("100.00"),
            is_taxable=True,
        )
        self.invoice.refresh_from_db()
        # total is 108.25; a payment of 108.25 is allowed, 108.26 is not.
        ok = Payment(invoice=self.invoice, payment_date=date.today(), amount=Decimal("108.25"))
        ok.full_clean()  # should not raise
        too_much = Payment(
            invoice=self.invoice, payment_date=date.today(), amount=Decimal("108.26")
        )
        with self.assertRaises(ValidationError):
            too_much.full_clean()

    def test_editing_line_item_cannot_reduce_total_below_amount_paid_with_tax(self):
        item = make_line_item(
            self.invoice,
            item_type=InvoiceLineItem.ItemType.PARTS,
            unit_price=Decimal("1000.00"),
            is_taxable=True,
        )
        self.invoice.refresh_from_db()
        # total 1082.50; record a payment near that total.
        Payment.objects.create(
            invoice=self.invoice,
            payment_date=date.today(),
            amount=Decimal("1000.00"),
            method=Payment.Method.CASH,
        )
        # Dropping to 900 taxable => total 974.25 < 1000 paid -> rejected.
        item.unit_price = Decimal("900.00")
        with self.assertRaises(ValidationError):
            item.save()

    def test_invoice_negative_tax_rate_rejected(self):
        self.invoice.tax_rate = Decimal("-0.01")
        with self.assertRaises(ValidationError):
            self.invoice.full_clean()


class InvoiceLineItemFormTaxabilityTests(TestCase):
    def test_form_exposes_taxable_field(self):
        form = InvoiceLineItemForm()
        self.assertIn("is_taxable", form.fields)
        self.assertEqual(form.fields["is_taxable"].label, "Taxable")

    def test_new_form_defaults_parts_taxable(self):
        form = InvoiceLineItemForm(initial={"item_type": "parts"})
        self.assertTrue(form.fields["is_taxable"].initial)

    def test_new_form_defaults_labor_not_taxable(self):
        form = InvoiceLineItemForm(initial={"item_type": "labor"})
        self.assertFalse(form.fields["is_taxable"].initial)


class InvoiceDetailTaxRenderingTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.ro = make_ro()
        self.invoice = make_invoice(self.ro)
        make_line_item(
            self.invoice,
            item_type=InvoiceLineItem.ItemType.PARTS,
            unit_price=Decimal("200.00"),
            is_taxable=True,
        )
        self.invoice.refresh_from_db()

    def test_detail_renders_tax_totals(self):
        url = reverse("billing:invoice_detail", kwargs={"pk": self.invoice.pk})
        response = self.client.get(url)
        self.assertContains(response, "Taxable subtotal")
        self.assertContains(response, "Sales tax")
        self.assertContains(response, "16.50")  # tax on 200 @ 8.25%
        self.assertContains(response, "216.50")  # total


class ConversionTaxTests(TestCase):
    def setUp(self):
        self.ro = make_ro(number="RO-CONV-TAX", vin="2T1BURHE0JC043821")
        self.user = make_user(username="conv-tax-user")
        self.estimate = Estimate.objects.create(
            repair_order=self.ro,
            estimate_number="EST-CONV-TAX",
            status=Estimate.Status.APPROVED,
            tax_rate=Decimal("0.0625"),
            approval_source=Estimate.ApprovalSource.CUSTOMER,
            approval_contact_name="Jane Smith",
            approved_at=timezone.now(),
        )
        EstimateLineItem.objects.create(
            estimate=self.estimate,
            item_type=EstimateLineItem.ItemType.LABOR,
            description="Labor",
            quantity=Decimal("1.00"),
            unit_price=Decimal("300.00"),
            is_taxable=False,
        )
        EstimateLineItem.objects.create(
            estimate=self.estimate,
            item_type=EstimateLineItem.ItemType.PARTS,
            description="Parts",
            quantity=Decimal("1.00"),
            unit_price=Decimal("200.00"),
            is_taxable=True,
        )
        self.estimate.refresh_from_db()

    def test_estimate_tax_snapshot(self):
        # 200 taxable @ 6.25% = 12.50; total 512.50
        self.assertEqual(self.estimate.taxable_subtotal, Decimal("200.00"))
        self.assertEqual(self.estimate.tax_amount, Decimal("12.50"))
        self.assertEqual(self.estimate.total_amount, Decimal("512.50"))

    def test_conversion_copies_tax_rate_and_taxability(self):
        invoice = convert_estimate_to_invoice(self.estimate, created_by=self.user)
        self.assertEqual(invoice.tax_rate, Decimal("0.0625"))
        items = {item.item_type: item for item in invoice.line_items.all()}
        self.assertFalse(items[InvoiceLineItem.ItemType.LABOR].is_taxable)
        self.assertTrue(items[InvoiceLineItem.ItemType.PARTS].is_taxable)

    def test_conversion_totals_match_estimate(self):
        invoice = convert_estimate_to_invoice(self.estimate, created_by=self.user)
        self.assertEqual(invoice.subtotal, Decimal("500.00"))
        self.assertEqual(invoice.taxable_subtotal, Decimal("200.00"))
        self.assertTrue(self.estimate.tax_breakdown_recorded)
        self.assertTrue(invoice.tax_breakdown_recorded)
        self.assertEqual(invoice.tax_amount, Decimal("12.50"))
        self.assertEqual(invoice.total_amount, self.estimate.total_amount)
