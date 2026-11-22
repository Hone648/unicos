from datetime import date
from decimal import Decimal

from billing.forms import InvoiceLineItemForm
from billing.models import Invoice
from billing.services import (
    InvoiceLineItemMutationBlocked,
    convert_estimate_to_invoice,
    create_invoice_line_item,
    edit_invoice_line_item,
    record_payment,
)
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from estimates.models import Estimate

BEFORE_SLICE_48 = [
    ("billing", "0003_invoice_source_estimate_and_more"),
    ("estimates", "0003_estimate_approval_contact_name_and_more"),
]
SLICE_48 = [(app, "0005_backfill_line_item_taxability") for app, _ in BEFORE_SLICE_48]
SLICE_49 = [(app, "0006_tax_breakdown_recorded") for app, _ in BEFORE_SLICE_48]


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


def invoice_snapshot(invoice):
    payments = list(
        invoice.payments.order_by("pk").values_list("pk", "payment_date", "amount", "method")
    )
    paid = sum((payment[2] for payment in payments), Decimal("0.00"))
    total = invoice.subtotal + invoice.tax_amount
    balance = max(total - paid, Decimal("0.00"))
    return invoice.subtotal, invoice.tax_amount, total, payments, invoice.status, balance


def estimate_snapshot(estimate):
    return estimate.estimated_total, estimate.status, estimate.approved_at


@override_settings(SHOP_SALES_TAX_RATE=Decimal("0.0825"))
class TaxUpgradeTests(TransactionTestCase):
    def setUp(self):
        self.addCleanup(migrate, SLICE_49)
        apps = migrate(BEFORE_SLICE_48)
        customer = apps.get_model("customers", "Customer").objects.create(
            customer_type="individual", first_name="Migration", last_name="Customer"
        )
        vehicle = apps.get_model("vehicles", "Vehicle").objects.create(
            customer=customer, vin="1HGBH41JXMN109186", make="Honda", model="Civic", year=2021
        )

        def order(number):
            return apps.get_model("repair_orders", "RepairOrder").objects.create(
                customer=customer, vehicle=vehicle, repair_order_number=number
            )

        old_invoice = apps.get_model("billing", "Invoice")
        old_invoice_line = apps.get_model("billing", "InvoiceLineItem")
        old_payment = apps.get_model("billing", "Payment")
        self.invoices = [
            old_invoice.objects.create(
                repair_order=order("RO-PAID"),
                invoice_number="INV-PAID",
                subtotal=Decimal("100.00"),
                tax_amount=Decimal("0.00"),
                status="paid",
            ),
            old_invoice.objects.create(
                repair_order=order("RO-MANUAL-TAX"),
                invoice_number="INV-MANUAL-TAX",
                subtotal=Decimal("150.00"),
                tax_amount=Decimal("12.34"),
                status="partially_paid",
            ),
        ]
        for invoice, paid in zip(self.invoices, ("100.00", "40.00"), strict=True):
            old_invoice_line.objects.create(
                invoice=invoice,
                item_type="parts",
                description="Replacement part",
                quantity=Decimal("1.00"),
                unit_price=invoice.subtotal,
            )
            old_payment.objects.create(
                invoice=invoice, payment_date=date(2025, 1, 3), amount=Decimal(paid), method="cash"
            )
        self.estimate = apps.get_model("estimates", "Estimate").objects.create(
            repair_order=order("RO-APPROVED"),
            estimate_number="EST-APPROVED",
            estimated_total=Decimal("100.00"),
            status="approved",
            approval_source="customer",
            approval_contact_name="Migration Customer",
            approved_at=timezone.now(),
        )
        apps.get_model("estimates", "EstimateLineItem").objects.create(
            estimate=self.estimate,
            item_type="parts",
            description="Approved part",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
        )

    def assert_current_invoices(self, before):
        for legacy, expected in zip(self.invoices, before, strict=True):
            invoice = Invoice.objects.get(pk=legacy.pk)
            self.assertEqual(invoice_snapshot(invoice), expected)
            self.assertEqual(invoice.total_amount, expected[2])
            self.assertEqual(invoice.amount_paid, expected[3][0][2])
            self.assertEqual(invoice.balance_due, expected[5])
            self.assertFalse(invoice.tax_breakdown_recorded)

    def test_upgrade_from_pre_tax_schema_preserves_financial_records_and_approved_amount(self):
        before_invoices = [invoice_snapshot(invoice) for invoice in self.invoices]
        before_estimate = estimate_snapshot(self.estimate)
        migrate(SLICE_49)

        self.assert_current_invoices(before_invoices)
        estimate = Estimate.objects.get(pk=self.estimate.pk)
        self.assertEqual(estimate_snapshot(estimate), before_estimate)
        self.assertFalse(estimate.tax_breakdown_recorded)
        self.assertFalse(estimate.line_items.get().is_taxable)
        self.assertEqual(estimate.tax_amount, Decimal("0.00"))
        self.assertEqual(estimate.total_amount, Decimal("100.00"))

        draft = convert_estimate_to_invoice(estimate)
        self.assertEqual(draft.status, Invoice.Status.DRAFT)
        self.assertFalse(draft.tax_breakdown_recorded)
        self.assertFalse(draft.line_items.get().is_taxable)
        self.assertEqual(draft.tax_amount, Decimal("0.00"))
        self.assertEqual(draft.total_amount, Decimal("100.00"))

        self.client.force_login(get_user_model().objects.create_superuser("migration-reviewer"))
        views = [
            (reverse("billing:invoice_detail", args=[self.invoices[1].pk]), "$12.34"),
            (reverse("estimates:detail", args=[estimate.pk]), "$100.00"),
            (reverse("estimates:print", args=[estimate.pk]), "$100.00"),
        ]
        for url, amount in views:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, amount)
                self.assertContains(response, "Tax breakdown unavailable")
                self.assertNotContains(response, "Taxable subtotal")
                self.assertNotContains(response, "Sales tax rate")
                self.assertNotContains(response, "<th>Taxable</th>", html=True)

    def test_historical_itemized_invoice_allows_nonfinancial_edits_and_payment(self):
        migrate(SLICE_49)
        invoice = Invoice.objects.get(pk=self.invoices[1].pk)
        line = invoice.line_items.get()
        form = InvoiceLineItemForm(
            {
                "item_type": "parts",
                "description": "Adjusted description",
                "quantity": "1.00",
                "unit_price": "150.00",
            },
            instance=line,
        )
        self.assertTrue(form.is_valid(), form.errors)
        edit_invoice_line_item(line, form.cleaned_data, actor=None)
        with self.assertRaisesMessage(InvoiceLineItemMutationBlocked, "Review the saved tax"):
            edit_invoice_line_item(line, {"unit_price": Decimal("200.00")}, actor=None)
        with self.assertRaisesMessage(InvoiceLineItemMutationBlocked, "Review the saved tax"):
            create_invoice_line_item(invoice, form.cleaned_data, actor=None)
        invoice.refresh_from_db()
        self.assertEqual(invoice.line_items.get().description, "Adjusted description")
        self.assertEqual(invoice.total_amount, Decimal("162.34"))
        self.assertEqual(invoice.tax_amount, Decimal("12.34"))

        record_payment(
            invoice,
            {"amount": Decimal("10.00"), "method": "cash", "payment_date": date(2025, 1, 4)},
            actor=None,
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PARTIALLY_PAID)
        self.assertEqual(invoice.balance_due, Decimal("112.34"))

    def test_reviewed_migrated_draft_invoice_can_be_repriced(self):
        apps = migrate(SLICE_48)
        old_invoice = apps.get_model("billing", "Invoice")
        old_line = apps.get_model("billing", "InvoiceLineItem")
        source = old_invoice.objects.get(pk=self.invoices[0].pk)
        source.payments.all().delete()
        source.status = "draft"
        source.taxable_subtotal = Decimal("100.00")
        source.tax_amount = Decimal("8.25")
        source.save()
        old_line.objects.filter(invoice=source).update(is_taxable=True)

        migrate(SLICE_49)
        invoice = Invoice.objects.get(pk=source.pk)
        line = invoice.line_items.get()
        self.assertEqual(invoice.total_amount, Decimal("108.25"))
        self.assertFalse(invoice.tax_breakdown_recorded)

        self.client.force_login(get_user_model().objects.create_superuser("tax-reviewer"))
        line_url = reverse("billing:line_item_edit", args=[line.pk])
        data = {
            "item_type": "parts",
            "description": "Replacement part",
            "quantity": "1.00",
            "unit_price": "200.00",
            "is_taxable": "on",
        }
        self.assertContains(self.client.post(line_url, data), "Review the saved tax")
        line.refresh_from_db()
        self.assertEqual(line.unit_price, Decimal("100.00"))

        admin_url = reverse("admin:billing_invoicelineitem_change", args=[line.pk])
        admin_data = dict(data, invoice=invoice.pk, _save="Save")
        self.assertContains(self.client.post(admin_url, admin_data), "Review the saved tax")
        line.refresh_from_db()
        self.assertEqual(line.unit_price, Decimal("100.00"))

        review_url = reverse("billing:invoice_tax_review", args=[invoice.pk])
        detail_url = reverse("billing:invoice_detail", args=[invoice.pk])
        self.assertContains(self.client.get(review_url), "$108.25")
        self.client.post(review_url, {"rate": "8.25"})
        invoice.refresh_from_db()
        self.assertFalse(invoice.tax_breakdown_recorded)
        self.assertRedirects(
            self.client.post(review_url, {"rate": "8.25", f"taxable_{line.pk}": "yes"}),
            detail_url,
        )
        line.is_taxable = False
        edit_invoice_line_item(line, {"description": "Updated description"}, actor=None)
        self.assertTrue(line.is_taxable)
        self.assertRedirects(
            self.client.post(line_url, data),
            reverse("repair_orders:detail", args=[invoice.repair_order_id]),
        )
        invoice.refresh_from_db()
        self.assertTrue(invoice.tax_breakdown_recorded)
        self.assertEqual(invoice.taxable_subtotal, Decimal("200.00"))
        self.assertEqual(invoice.tax_amount, Decimal("16.50"))
        self.assertEqual(invoice.total_amount, Decimal("216.50"))
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)

    def test_migrated_estimate_requires_review_before_line_edits_or_deletion(self):
        apps = migrate(SLICE_48)
        old = apps.get_model("estimates", "Estimate").objects.get(pk=self.estimate.pk)
        old.status = "draft"
        old.save(update_fields=["status"])
        migrate(SLICE_49)

        self.client.force_login(get_user_model().objects.create_superuser("estimate-reviewer"))
        estimate = Estimate.objects.get(pk=old.pk)
        line = estimate.line_items.get()
        data = {
            "item_type": "parts",
            "description": "Approved part",
            "quantity": "1.00",
            "unit_price": "200.00",
            "is_taxable": "on",
        }
        line_url = reverse("estimates:line_item_edit", args=[line.pk])
        self.assertContains(self.client.post(line_url, data), "Review the saved tax")
        admin_url = reverse("admin:estimates_estimatelineitem_change", args=[line.pk])
        admin_data = dict(data, estimate=estimate.pk, sort_order=0, _save="Save")
        self.assertContains(self.client.post(admin_url, admin_data), "Review the saved tax")
        delete_url = reverse("estimates:line_item_delete", args=[line.pk])
        detail_url = reverse("estimates:detail", args=[estimate.pk])
        self.assertRedirects(self.client.post(delete_url), detail_url)
        self.assertTrue(estimate.line_items.filter(pk=line.pk).exists())
        self.assertRedirects(
            self.client.post(
                reverse("estimates:tax_review", args=[estimate.pk]),
                {"rate": "8.25", f"taxable_{line.pk}": "yes"},
            ),
            detail_url,
        )
        line.description = "Updated description"
        line.save()
        self.assertTrue(line.is_taxable)
        self.assertRedirects(self.client.post(line_url, data), detail_url)
        estimate.refresh_from_db()
        self.assertEqual(estimate.tax_amount, Decimal("16.50"))
        self.assertEqual(estimate.total_amount, Decimal("216.50"))

    def test_upgrade_with_both_original_backfills_recorded_preserves_current_amounts(self):
        apps = migrate(SLICE_48)
        for migration in SLICE_48:
            self.assertIn(migration, MigrationRecorder(connection).applied_migrations())

        # Use the rows the original 0005 operations would leave for these fixtures.
        invoice_model = apps.get_model("billing", "Invoice")
        invoice_line_model = apps.get_model("billing", "InvoiceLineItem")
        invoice_line_model.objects.update(is_taxable=True)
        invoices = [invoice_model.objects.get(pk=legacy.pk) for legacy in self.invoices]
        for invoice, tax in zip(invoices, ("8.25", "12.38"), strict=True):
            invoice.taxable_subtotal = invoice.subtotal
            invoice.tax_amount = Decimal(tax)
            invoice.save(update_fields=["taxable_subtotal", "tax_amount"])
        before_invoices = [invoice_snapshot(invoice) for invoice in invoices]

        old_estimate = apps.get_model("estimates", "Estimate").objects.get(pk=self.estimate.pk)
        old_estimate.line_items.update(is_taxable=True)
        old_estimate.taxable_subtotal = Decimal("100.00")
        old_estimate.tax_amount = Decimal("8.25")
        old_estimate.save(update_fields=["taxable_subtotal", "tax_amount"])
        before_estimate = estimate_snapshot(old_estimate)
        migrate(SLICE_49)

        self.assert_current_invoices(before_invoices)
        for legacy in self.invoices:
            invoice = Invoice.objects.get(pk=legacy.pk)
            self.assertEqual(invoice.tax_rate, Decimal("0.0825"))
            self.assertEqual(invoice.taxable_subtotal, invoice.subtotal)
            self.assertTrue(invoice.line_items.get().is_taxable)

        estimate = Estimate.objects.get(pk=self.estimate.pk)
        self.assertEqual(estimate_snapshot(estimate), before_estimate)
        self.assertFalse(estimate.tax_breakdown_recorded)
        self.assertEqual(estimate.tax_rate, Decimal("0.0825"))
        self.assertEqual(estimate.taxable_subtotal, Decimal("100.00"))
        self.assertEqual(estimate.tax_amount, Decimal("8.25"))
        self.assertEqual(estimate.total_amount, Decimal("108.25"))
        self.assertTrue(estimate.line_items.get().is_taxable)
        draft = convert_estimate_to_invoice(estimate)
        self.assertEqual(draft.total_amount, Decimal("108.25"))
        self.assertFalse(draft.tax_breakdown_recorded)
