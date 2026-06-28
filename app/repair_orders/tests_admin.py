from django.contrib import admin
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.contrib.auth import get_user_model

from customers.models import Customer
from repair_orders.admin import RepairOrderAdmin, RepairOrderStatusHistoryAdmin
from repair_orders.models import RepairOrder, RepairOrderStatusHistory
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username="staffuser", **kwargs):
    return get_user_model().objects.create_user(
        username=username, password="pw-test-12345", **kwargs
    )


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
            self.customer, self.vehicle, number="RO-ALREADY",
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
        self.admin_instance = RepairOrderStatusHistoryAdmin(
            RepairOrderStatusHistory, admin.site
        )
        user = make_user()
        self.request = make_request(user)

    def test_has_add_permission_returns_false(self):
        self.assertFalse(self.admin_instance.has_add_permission(self.request))

    def test_has_change_permission_returns_false(self):
        self.assertFalse(self.admin_instance.has_change_permission(self.request))

    def test_has_delete_permission_returns_false(self):
        self.assertFalse(self.admin_instance.has_delete_permission(self.request))
