from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from billing.models import Invoice, InvoiceLineItem, Payment
from billing.services import (
    EstimateInvoiceConversionBlocked,
    InvoiceIssueBlocked,
    InvoiceLineItemMutationBlocked,
    InvoiceVoidBlocked,
    PaymentRecordingBlocked,
    create_invoice_line_item,
    convert_estimate_to_invoice,
    edit_invoice_line_item,
    estimate_can_convert_to_invoice,
    issue_invoice,
    record_payment,
    void_invoice,
)
from customers.models import Customer
from estimates.models import Estimate, EstimateLineItem
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


def make_repair_order(number="RO-CONV-001", vin=VALID_VIN):
    customer = Customer.objects.create(
        customer_type=Customer.CustomerType.INDIVIDUAL,
        first_name="Conv",
        last_name="Test",
    )
    vehicle = Vehicle.objects.create(
        customer=customer,
        vin=vin,
        make="Honda",
        model="Civic",
        year=2021,
    )
    return RepairOrder.objects.create(
        customer=customer,
        vehicle=vehicle,
        repair_order_number=number,
    )


def make_invoice(repair_order, number="INV-SVC-001", **kwargs):
    defaults = {
        "invoice_number": number,
        "status": Invoice.Status.DRAFT,
        "subtotal": Decimal("100.00"),
        "tax_amount": Decimal("0.00"),
    }
    defaults.update(kwargs)
    return Invoice.objects.create(repair_order=repair_order, **defaults)


def make_invoice_line_item(invoice, **kwargs):
    defaults = {
        "item_type": InvoiceLineItem.ItemType.LABOR,
        "description": "Service labor",
        "quantity": Decimal("1.00"),
        "unit_price": Decimal("100.00"),
    }
    defaults.update(kwargs)
    return InvoiceLineItem.objects.create(invoice=invoice, **defaults)


def make_payment(invoice, amount):
    return Payment.objects.create(
        invoice=invoice,
        payment_date=date.today(),
        amount=amount,
        method=Payment.Method.CASH,
    )


def make_estimate(repair_order, number="EST-CONV-001", status=Estimate.Status.APPROVED):
    estimate = Estimate.objects.create(
        repair_order=repair_order,
        estimate_number=number,
        status=status,
    )
    if status == Estimate.Status.APPROVED:
        estimate.approval_source = Estimate.ApprovalSource.CUSTOMER
        estimate.approval_contact_name = "Jane Smith"
        estimate.approval_reference = "APPROVAL-REF"
        estimate.approval_note = "Approved for conversion."
        estimate.approved_at = timezone.now()
        estimate.save(update_fields=[
            "approval_source",
            "approval_contact_name",
            "approval_reference",
            "approval_note",
            "approved_at",
            "updated_at",
        ])
    return estimate


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

    def test_approved_without_approval_capture_is_blocked(self):
        estimate = Estimate.objects.create(
            repair_order=self.ro,
            estimate_number="EST-NO-CAPTURE",
            status=Estimate.Status.APPROVED,
        )
        add_line_item(estimate)
        with self.assertRaises(EstimateInvoiceConversionBlocked) as ctx:
            convert_estimate_to_invoice(estimate, created_by=self.user)
        self.assertIn("approval capture", str(ctx.exception))
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


class InvoiceIssueServiceTests(TestCase):
    def setUp(self):
        self.ro = make_repair_order(number="RO-ISSUE-SVC")
        self.invoice = make_invoice(self.ro, number="INV-ISSUE-SVC")
        self.user = get_user_model().objects.create_user(
            username="issue-svc", password="pw-test-12345"
        )

    def test_issue_invoice_sets_status_date_and_actor(self):
        issue_invoice(self.invoice, actor=self.user)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)
        self.assertIsNotNone(self.invoice.issued_at)
        self.assertEqual(self.invoice.updated_by, self.user)

    def test_issue_invoice_preserves_existing_issued_at(self):
        original_date = date(2025, 3, 15)
        self.invoice.issued_at = original_date
        self.invoice.save(update_fields=["issued_at", "updated_at"])
        issue_invoice(self.invoice, actor=self.user)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.issued_at, original_date)

    def test_issue_invoice_blocks_non_draft_invoice(self):
        self.invoice.status = Invoice.Status.ISSUED
        self.invoice.save(update_fields=["status", "updated_at"])
        with self.assertRaises(InvoiceIssueBlocked):
            issue_invoice(self.invoice, actor=self.user)

    def test_issue_invoice_blocks_final_repair_order(self):
        self.ro._apply_status_change(RepairOrder.Status.DELIVERED, changed_by=self.user)
        with self.assertRaises(InvoiceIssueBlocked):
            issue_invoice(self.invoice, actor=self.user)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.DRAFT)


class InvoiceVoidServiceTests(TestCase):
    def setUp(self):
        self.ro = make_repair_order(number="RO-VOID-SVC")
        self.invoice = make_invoice(self.ro, number="INV-VOID-SVC")
        self.user = get_user_model().objects.create_user(
            username="void-svc", password="pw-test-12345"
        )

    def test_void_invoice_sets_status_and_actor(self):
        void_invoice(self.invoice, actor=self.user)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.VOID)
        self.assertEqual(self.invoice.updated_by, self.user)

    def test_void_invoice_blocks_already_void_invoice(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])
        with self.assertRaises(InvoiceVoidBlocked):
            void_invoice(self.invoice, actor=self.user)

    def test_void_invoice_blocks_final_repair_order(self):
        self.ro._apply_status_change(RepairOrder.Status.DELIVERED, changed_by=self.user)
        with self.assertRaises(InvoiceVoidBlocked):
            void_invoice(self.invoice, actor=self.user)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.DRAFT)


class RecordPaymentServiceTests(TestCase):
    def setUp(self):
        self.ro = make_repair_order(number="RO-PAY-SVC")
        self.invoice = make_invoice(
            self.ro,
            number="INV-PAY-SVC",
            status=Invoice.Status.ISSUED,
            subtotal=Decimal("100.00"),
        )
        self.user = get_user_model().objects.create_user(
            username="pay-svc", password="pw-test-12345"
        )

    def _payment_data(self, amount=Decimal("50.00")):
        return {
            "payment_date": date.today(),
            "amount": amount,
            "method": Payment.Method.CASH,
            "reference": "",
            "notes": "",
        }

    def test_record_payment_creates_payment_and_sets_actor(self):
        payment = record_payment(self.invoice, self._payment_data(), actor=self.user)
        self.assertEqual(payment.invoice, self.invoice)
        self.assertEqual(payment.received_by, self.user)

    def test_record_payment_syncs_invoice_status(self):
        record_payment(self.invoice, self._payment_data(), actor=self.user)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)

    def test_record_full_payment_marks_invoice_paid(self):
        record_payment(
            self.invoice,
            self._payment_data(amount=Decimal("100.00")),
            actor=self.user,
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)

    def test_record_payment_rejects_overpayment(self):
        with self.assertRaises(PaymentRecordingBlocked):
            record_payment(
                self.invoice,
                self._payment_data(amount=Decimal("101.00")),
                actor=self.user,
            )
        self.assertFalse(Payment.objects.filter(invoice=self.invoice).exists())

    def test_record_payment_rejects_non_positive_amount(self):
        with self.assertRaises(PaymentRecordingBlocked):
            record_payment(
                self.invoice,
                self._payment_data(amount=Decimal("0.00")),
                actor=self.user,
            )
        self.assertFalse(Payment.objects.filter(invoice=self.invoice).exists())

    def test_record_payment_blocks_void_invoice(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])
        with self.assertRaises(PaymentRecordingBlocked):
            record_payment(self.invoice, self._payment_data(), actor=self.user)

    def test_record_payment_blocks_final_repair_order(self):
        self.ro._apply_status_change(RepairOrder.Status.DELIVERED, changed_by=self.user)
        with self.assertRaises(PaymentRecordingBlocked):
            record_payment(self.invoice, self._payment_data(), actor=self.user)

    def test_record_payment_locks_invoice_row(self):
        with mock.patch.object(
            Invoice.objects,
            "select_for_update",
            wraps=Invoice.objects.select_for_update,
        ) as select_for_update:
            record_payment(self.invoice, self._payment_data(), actor=self.user)

        select_for_update.assert_called_once()


class InvoiceLineItemServiceTests(TestCase):
    def setUp(self):
        self.ro = make_repair_order(number="RO-LINE-SVC")
        self.invoice = make_invoice(
            self.ro,
            number="INV-LINE-SVC",
            subtotal=Decimal("0.00"),
        )
        self.user = get_user_model().objects.create_user(
            username="line-svc", password="pw-test-12345"
        )

    def _line_item_data(self, **overrides):
        data = {
            "item_type": InvoiceLineItem.ItemType.LABOR,
            "description": "Service line",
            "quantity": Decimal("2.00"),
            "unit_price": Decimal("50.00"),
        }
        data.update(overrides)
        return data

    def test_create_invoice_line_item_creates_item_and_recalculates_subtotal(self):
        create_invoice_line_item(self.invoice, self._line_item_data(), actor=self.user)
        self.invoice.refresh_from_db()
        self.assertEqual(InvoiceLineItem.objects.filter(invoice=self.invoice).count(), 1)
        self.assertEqual(self.invoice.subtotal, Decimal("100.00"))

    def test_create_invoice_line_item_blocks_void_invoice(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])
        with self.assertRaises(InvoiceLineItemMutationBlocked):
            create_invoice_line_item(
                self.invoice,
                self._line_item_data(),
                actor=self.user,
            )

    def test_create_invoice_line_item_blocks_final_repair_order(self):
        self.ro._apply_status_change(RepairOrder.Status.DELIVERED, changed_by=self.user)
        with self.assertRaises(InvoiceLineItemMutationBlocked):
            create_invoice_line_item(
                self.invoice,
                self._line_item_data(),
                actor=self.user,
            )

    def test_edit_invoice_line_item_updates_item_and_recalculates_subtotal(self):
        line_item = make_invoice_line_item(self.invoice)
        edit_invoice_line_item(
            line_item,
            self._line_item_data(description="Updated", unit_price=Decimal("75.00")),
            actor=self.user,
        )
        line_item.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(line_item.description, "Updated")
        self.assertEqual(self.invoice.subtotal, Decimal("150.00"))

    def test_edit_invoice_line_item_blocks_total_below_amount_paid(self):
        line_item = make_invoice_line_item(self.invoice)
        make_payment(self.invoice, Decimal("90.00"))
        with self.assertRaises(InvoiceLineItemMutationBlocked):
            edit_invoice_line_item(
                line_item,
                self._line_item_data(quantity=Decimal("1.00"), unit_price=Decimal("50.00")),
                actor=self.user,
            )
        line_item.refresh_from_db()
        self.invoice.refresh_from_db()
        self.assertEqual(line_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.invoice.subtotal, Decimal("100.00"))
