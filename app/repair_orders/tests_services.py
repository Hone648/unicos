from datetime import date
from decimal import Decimal

from accounts.authorization import ROLE_MANAGER
from billing.models import Invoice, Payment
from customers.models import Customer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from repair_orders.models import RepairOrder, RepairOrderStatusHistory
from repair_orders.services import (
    RepairOrderLifecycleError,
    RepairOrderStatusTransitionBlocked,
    transition_repair_order_status,
)
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(username="svc-user", **kwargs):
    user = get_user_model().objects.create_user(
        username=username, password="pw-test-12345", **kwargs
    )
    user.groups.add(Group.objects.get_or_create(name=ROLE_MANAGER)[0])
    return user


def make_customer(**kwargs):
    defaults = {
        "customer_type": Customer.CustomerType.INDIVIDUAL,
        "first_name": "Svc",
        "last_name": "Test",
    }
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


def make_vehicle(customer, vin=VALID_VIN, **kwargs):
    return Vehicle.objects.create(
        customer=customer, vin=vin, make="Honda", model="Civic", year=2021, **kwargs
    )


def make_repair_order(customer, vehicle, number="RO-SVC-001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number=number, **kwargs
    )


def make_invoice(repair_order, number="INV-SVC-001", **kwargs):
    defaults = {"subtotal": Decimal("400.00"), "tax_amount": Decimal("40.00")}
    defaults.update(kwargs)
    return Invoice.objects.create(repair_order=repair_order, invoice_number=number, **defaults)


def make_payment(invoice, amount=Decimal("440.00"), **kwargs):
    defaults = {"payment_date": date.today(), "method": Payment.Method.CASH}
    defaults.update(kwargs)
    return Payment.objects.create(invoice=invoice, amount=amount, **defaults)


# ---------------------------------------------------------------------------
# transition_repair_order_status service tests
# ---------------------------------------------------------------------------


class TransitionRepairOrderStatusTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.user = make_user()

    def test_non_final_transition_succeeds(self):
        transition_repair_order_status(self.ro, RepairOrder.Status.ESTIMATING)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.ESTIMATING)

    def test_successful_transition_updates_status(self):
        transition_repair_order_status(self.ro, RepairOrder.Status.IN_REPAIR)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.IN_REPAIR)

    def test_successful_transition_creates_status_history(self):
        count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        transition_repair_order_status(self.ro, RepairOrder.Status.ESTIMATING, changed_by=self.user)
        count_after = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self.assertEqual(count_after, count_before + 1)

    def test_successful_transition_records_changed_by(self):
        transition_repair_order_status(self.ro, RepairOrder.Status.ESTIMATING, changed_by=self.user)
        latest = (
            RepairOrderStatusHistory.objects.filter(repair_order=self.ro)
            .order_by("-changed_at", "-id")
            .first()
        )
        self.assertEqual(latest.changed_by, self.user)

    def test_successful_transition_records_note(self):
        transition_repair_order_status(
            self.ro, RepairOrder.Status.ESTIMATING, note="approved by phone"
        )
        latest = (
            RepairOrderStatusHistory.objects.filter(repair_order=self.ro)
            .order_by("-changed_at", "-id")
            .first()
        )
        self.assertEqual(latest.note, "approved by phone")

    def test_final_transition_with_no_invoice_succeeds(self):
        self.ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        transition_repair_order_status(self.ro, RepairOrder.Status.DELIVERED)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.DELIVERED)

    def test_final_transition_with_fully_paid_invoice_succeeds(self):
        self.ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        invoice = make_invoice(self.ro)
        make_payment(invoice, Decimal("440.00"))
        transition_repair_order_status(self.ro, RepairOrder.Status.DELIVERED)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.DELIVERED)

    def test_final_transition_with_void_invoice_succeeds(self):
        self.ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        invoice = make_invoice(self.ro)
        invoice.status = Invoice.Status.VOID
        invoice.save(update_fields=["status", "updated_at"])
        transition_repair_order_status(self.ro, RepairOrder.Status.DELIVERED)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.DELIVERED)

    def test_final_transition_with_unpaid_invoice_raises_blocked(self):
        self.ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        make_invoice(self.ro)  # balance_due = 440 > 0
        with self.assertRaises(RepairOrderStatusTransitionBlocked):
            transition_repair_order_status(self.ro, RepairOrder.Status.DELIVERED)

    def test_blocked_transition_leaves_status_unchanged(self):
        self.ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        make_invoice(self.ro)
        original_status = self.ro.status
        try:
            transition_repair_order_status(self.ro, RepairOrder.Status.DELIVERED)
        except RepairOrderStatusTransitionBlocked:
            pass
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, original_status)

    def test_blocked_transition_does_not_create_history(self):
        self.ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        make_invoice(self.ro)
        count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        try:
            transition_repair_order_status(self.ro, RepairOrder.Status.DELIVERED)
        except RepairOrderStatusTransitionBlocked:
            pass
        count_after = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self.assertEqual(count_before, count_after)

    def test_set_status_uses_lifecycle_rule_boundary(self):
        """set_status routes through the service and blocks when lifecycle rules apply."""
        self.ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        make_invoice(self.ro)  # unpaid → blocks final status
        with self.assertRaises(RepairOrderStatusTransitionBlocked):
            self.ro.set_status(RepairOrder.Status.DELIVERED)

    def test_blocked_error_is_repair_order_lifecycle_error_subclass(self):
        self.ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        make_invoice(self.ro)
        with self.assertRaises(RepairOrderLifecycleError):
            transition_repair_order_status(self.ro, RepairOrder.Status.DELIVERED)

    def test_blocked_error_message_includes_invoice_number(self):
        self.ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        make_invoice(self.ro, number="INV-BLOCK-MSG")
        try:
            transition_repair_order_status(self.ro, RepairOrder.Status.DELIVERED)
            self.fail("Expected RepairOrderStatusTransitionBlocked")
        except RepairOrderStatusTransitionBlocked as exc:
            self.assertIn("INV-BLOCK-MSG", str(exc))

    def test_canceled_final_status_also_blocked_by_unpaid_invoice(self):
        make_invoice(self.ro)
        with self.assertRaises(RepairOrderStatusTransitionBlocked):
            transition_repair_order_status(
                self.ro,
                RepairOrder.Status.CANCELED,
                changed_by=self.user,
                action="cancel",
                reason="Customer canceled",
            )

    def test_closed_final_status_also_blocked_by_unpaid_invoice(self):
        self.ro._apply_status_change(RepairOrder.Status.DELIVERED)
        make_invoice(self.ro)
        with self.assertRaises(RepairOrderStatusTransitionBlocked):
            transition_repair_order_status(self.ro, RepairOrder.Status.CLOSED)

    def test_invalid_status_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            transition_repair_order_status(self.ro, "not_a_real_status")

    def test_service_returns_repair_order_on_success(self):
        result = transition_repair_order_status(self.ro, RepairOrder.Status.ESTIMATING)
        self.assertIs(result, self.ro)
