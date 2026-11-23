from datetime import date
from decimal import Decimal

from accounts.authorization import ROLE_MANAGER
from billing.models import Invoice, Payment
from customers.models import Customer
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from repair_orders.admin import RepairOrderAdmin, RepairOrderStatusHistoryAdmin
from repair_orders.models import RepairOrder, RepairOrderStatusHistory
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"
VALID_VIN_3 = "5NPE24AF6FH002401"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_user(username="staffuser", **kwargs):
    user = get_user_model().objects.create_user(
        username=username, password="pw-test-12345", **kwargs
    )
    user.groups.add(Group.objects.get_or_create(name=ROLE_MANAGER)[0])
    return user


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


def make_invoice(repair_order, number="INV-0001", **kwargs):
    defaults = {"subtotal": Decimal("400.00"), "tax_amount": Decimal("40.00")}
    defaults.update(kwargs)
    return Invoice.objects.create(repair_order=repair_order, invoice_number=number, **defaults)


def make_payment(invoice, amount=Decimal("440.00"), **kwargs):
    defaults = {"payment_date": date.today(), "method": Payment.Method.CASH}
    defaults.update(kwargs)
    return Payment.objects.create(invoice=invoice, amount=amount, **defaults)


def make_request(user):
    """Return a POST request with message storage attached, suitable for admin testing."""
    factory = RequestFactory()
    request = factory.post("/")
    request.user = user
    # message_user() requires a session and a message backend on the request.
    setattr(request, "session", "session")
    setattr(request, "_messages", FallbackStorage(request))
    return request


# ---------------------------------------------------------------------------
# RepairOrderAdmin.save_model tests
# ---------------------------------------------------------------------------


class RepairOrderAdminSaveModelTests(TestCase):
    def setUp(self):
        self.admin_instance = RepairOrderAdmin(RepairOrder, admin.site)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)

    def test_save_model_sets_created_by_and_updated_by_on_new_repair_order(self):
        user = make_user()
        request = make_request(user)
        ro = RepairOrder(
            customer=self.customer,
            vehicle=self.vehicle,
            repair_order_number="RO-NEW",
        )
        self.admin_instance.save_model(request, ro, None, change=False)
        self.assertEqual(ro.created_by, user)
        self.assertEqual(ro.updated_by, user)

    def test_save_model_updates_updated_by_on_existing_repair_order(self):
        creator = make_user(username="creator")
        ro = make_repair_order(self.customer, self.vehicle, created_by=creator)

        updater = make_user(username="updater")
        request = make_request(updater)
        self.admin_instance.save_model(request, ro, None, change=True)

        ro.refresh_from_db()
        self.assertEqual(ro.updated_by, updater)


# ---------------------------------------------------------------------------
# RepairOrderAdmin action tests
# ---------------------------------------------------------------------------


class RepairOrderAdminActionTests(TestCase):
    def setUp(self):
        self.admin_instance = RepairOrderAdmin(RepairOrder, admin.site)
        self.user = make_user()
        self.request = make_request(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)

    def test_action_changes_status_and_creates_history(self):
        ro = make_repair_order(self.customer, self.vehicle)
        queryset = RepairOrder.objects.filter(pk=ro.pk)

        self.admin_instance.mark_estimating(self.request, queryset)

        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.ESTIMATING)
        # Initial history (intake) + status-change history (estimating) = 2
        self.assertEqual(ro.status_history.count(), 2)

    def test_action_skips_repair_order_already_in_target_status(self):
        ro = make_repair_order(
            self.customer,
            self.vehicle,
            number="RO-ALREADY",
            status=RepairOrder.Status.ESTIMATING,
        )
        history_before = ro.status_history.count()
        queryset = RepairOrder.objects.filter(pk=ro.pk)

        self.admin_instance.mark_estimating(self.request, queryset)

        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.ESTIMATING)
        # No additional history row should have been created.
        self.assertEqual(ro.status_history.count(), history_before)


# ---------------------------------------------------------------------------
# RepairOrderStatusHistoryAdmin permission tests
# ---------------------------------------------------------------------------


class RepairOrderStatusHistoryAdminPermissionTests(TestCase):
    def setUp(self):
        self.admin_instance = RepairOrderStatusHistoryAdmin(RepairOrderStatusHistory, admin.site)
        user = make_user()
        self.request = make_request(user)

    def test_has_add_permission_returns_false(self):
        self.assertFalse(self.admin_instance.has_add_permission(self.request))

    def test_has_change_permission_returns_false(self):
        self.assertFalse(self.admin_instance.has_change_permission(self.request))

    def test_has_delete_permission_returns_false(self):
        self.assertFalse(self.admin_instance.has_delete_permission(self.request))


# ---------------------------------------------------------------------------
# Admin action lifecycle-block tests
# ---------------------------------------------------------------------------


class RepairOrderAdminActionLifecycleTests(TestCase):
    """Admin bulk status actions obey the unpaid-invoice final-status block."""

    def setUp(self):
        self.admin_instance = RepairOrderAdmin(RepairOrder, admin.site)
        self.user = make_user(username="admin-lifecycle")
        self.request = make_request(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN_2)

    def _ro(self, number, vin=None, **kwargs):
        v = make_vehicle(self.customer, vin=vin or VALID_VIN_3) if vin else self.vehicle
        return make_repair_order(
            self.customer, v, number=number, status=RepairOrder.Status.DELIVERED, **kwargs
        )

    def test_mark_closed_blocked_when_unpaid_invoice_exists(self):
        ro = self._ro("RO-CLOSE-BLOCK")
        make_invoice(ro, number="INV-CLOSE-BLOCK")  # balance_due = 440 > 0
        queryset = RepairOrder.objects.filter(pk=ro.pk)
        self.admin_instance.mark_closed(self.request, queryset)
        ro.refresh_from_db()
        self.assertNotEqual(ro.status, RepairOrder.Status.CLOSED)

    def test_mark_canceled_blocked_when_unpaid_invoice_exists(self):
        ro = self._ro("RO-CANCEL-BLOCK", vin=VALID_VIN_3)
        ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        self.request.POST = self.request.POST.copy()
        self.request.POST["transition_reason"] = "Customer canceled"
        make_invoice(ro, number="INV-CANCEL-BLOCK")
        queryset = RepairOrder.objects.filter(pk=ro.pk)
        self.admin_instance.mark_canceled(self.request, queryset)
        ro.refresh_from_db()
        self.assertNotEqual(ro.status, RepairOrder.Status.CANCELED)
        self.assertTrue(any("balance due" in str(message) for message in self.request._messages))

    def test_mark_closed_blocked_transition_does_not_create_history(self):
        ro = self._ro("RO-CLOSE-HIST-BLOCK")
        make_invoice(ro, number="INV-HIST-BLOCK")
        count_before = ro.status_history.count()
        queryset = RepairOrder.objects.filter(pk=ro.pk)
        self.admin_instance.mark_closed(self.request, queryset)
        ro.refresh_from_db()
        self.assertEqual(ro.status_history.count(), count_before)

    def test_mark_closed_allowed_with_no_invoice(self):
        ro = self._ro("RO-CLOSE-ALLOW")
        queryset = RepairOrder.objects.filter(pk=ro.pk)
        self.admin_instance.mark_closed(self.request, queryset)
        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.CLOSED)

    def test_mark_closed_allowed_with_fully_paid_invoice(self):
        ro = self._ro("RO-CLOSE-PAID")
        invoice = make_invoice(ro, number="INV-CLOSE-PAID")
        make_payment(invoice, Decimal("440.00"))  # fully paid
        queryset = RepairOrder.objects.filter(pk=ro.pk)
        self.admin_instance.mark_closed(self.request, queryset)
        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.CLOSED)

    def test_mark_closed_allowed_with_void_invoice(self):
        ro = self._ro("RO-CLOSE-VOID")
        invoice = make_invoice(ro, number="INV-CLOSE-VOID")
        invoice.status = Invoice.Status.VOID
        invoice.save(update_fields=["status", "updated_at"])
        queryset = RepairOrder.objects.filter(pk=ro.pk)
        self.admin_instance.mark_closed(self.request, queryset)
        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.CLOSED)


# ---------------------------------------------------------------------------
# Admin save_model status routing tests
# ---------------------------------------------------------------------------


class MockStatusChangeForm:
    """Minimal form stub for save_model routing tests."""

    def __init__(self, initial_status, new_status=None):
        self.initial = {"status": initial_status}
        if new_status is not None and new_status != initial_status:
            self.changed_data = ["status"]
        else:
            self.changed_data = []


class RepairOrderAdminSaveModelStatusRoutingTests(TestCase):
    """Admin save_model routes status changes through the lifecycle service."""

    def setUp(self):
        self.admin_instance = RepairOrderAdmin(RepairOrder, admin.site)
        self.user = make_user(username="admin-save-model")
        self.request = make_request(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN_2)

    def test_save_model_blocks_final_status_when_unpaid_invoice_exists(self):
        ro = make_repair_order(
            self.customer,
            self.vehicle,
            number="RO-ADMIN-FORM-BLOCK",
            status=RepairOrder.Status.READY_FOR_PICKUP,
        )
        make_invoice(ro, number="INV-ADMIN-FORM-BLOCK")  # balance_due > 0
        form = MockStatusChangeForm(
            initial_status=RepairOrder.Status.READY_FOR_PICKUP,
            new_status=RepairOrder.Status.DELIVERED,
        )
        ro.status = RepairOrder.Status.DELIVERED  # simulate form applying new value
        self.admin_instance.save_model(self.request, ro, form, change=True)
        ro.refresh_from_db()
        self.assertNotEqual(ro.status, RepairOrder.Status.DELIVERED)

    def test_save_model_allows_non_final_status_change(self):
        ro = make_repair_order(self.customer, self.vehicle, number="RO-ADMIN-FORM-NON-FINAL")
        form = MockStatusChangeForm(
            initial_status=RepairOrder.Status.INTAKE,
            new_status=RepairOrder.Status.IN_REPAIR,
        )
        ro.status = RepairOrder.Status.IN_REPAIR
        self.admin_instance.save_model(self.request, ro, form, change=True)
        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.IN_REPAIR)

    def test_save_model_allows_final_status_when_no_invoice(self):
        ro = make_repair_order(
            self.customer,
            self.vehicle,
            number="RO-ADMIN-FORM-FINAL-OK",
            status=RepairOrder.Status.READY_FOR_PICKUP,
        )
        form = MockStatusChangeForm(
            initial_status=RepairOrder.Status.READY_FOR_PICKUP,
            new_status=RepairOrder.Status.DELIVERED,
        )
        ro.status = RepairOrder.Status.DELIVERED
        self.admin_instance.save_model(self.request, ro, form, change=True)
        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.DELIVERED)
