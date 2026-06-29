from decimal import Decimal

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.urls import reverse

from customers.models import Customer
from estimates.admin import EstimateAdmin
from estimates.models import Estimate
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


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
        customer=customer, vehicle=vehicle, repair_order_number="RO-EST-ADM-001"
    )


def make_request(user):
    factory = RequestFactory()
    request = factory.post("/")
    request.user = user
    setattr(request, "session", "session")
    setattr(request, "_messages", FallbackStorage(request))
    return request


class EstimateAdminRegistrationTests(TestCase):
    def test_estimate_admin_is_registered(self):
        self.assertIn(Estimate, admin.site._registry)
        self.assertIs(admin.site._registry[Estimate].__class__, EstimateAdmin)


class EstimateAdminSaveModelTests(TestCase):
    def setUp(self):
        self.admin_instance = EstimateAdmin(Estimate, admin.site)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_save_model_sets_created_and_updated_by_on_new(self):
        user = make_user()
        request = make_request(user)
        estimate = Estimate(
            repair_order=self.ro,
            estimate_number="EST-ADM-NEW",
            estimated_total=Decimal("100.00"),
        )
        self.admin_instance.save_model(request, estimate, None, change=False)
        self.assertEqual(estimate.created_by, user)
        self.assertEqual(estimate.updated_by, user)

    def test_save_model_updates_updated_by_on_existing(self):
        creator = make_user("creator")
        estimate = Estimate.objects.create(
            repair_order=self.ro,
            estimate_number="EST-ADM-EXIST",
            created_by=creator,
            updated_by=creator,
        )
        updater = make_user("updater")
        request = make_request(updater)
        self.admin_instance.save_model(request, estimate, None, change=True)
        estimate.refresh_from_db()
        self.assertEqual(estimate.updated_by, updater)

    def test_customer_display_returns_customer(self):
        estimate = Estimate.objects.create(
            repair_order=self.ro, estimate_number="EST-ADM-DISP"
        )
        self.assertEqual(self.admin_instance.customer_display(estimate), self.customer)


class EstimateAdminChangeListTests(TestCase):
    def setUp(self):
        self.client.force_login(make_superuser())
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle)
        self.estimate = Estimate.objects.create(
            repair_order=ro,
            estimate_number="EST-ADM-LIST",
            insurance_company="Acme",
        )

    def test_changelist_loads(self):
        url = reverse("admin:estimates_estimate_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EST-ADM-LIST")

    def test_changelist_search_finds_estimate(self):
        url = reverse("admin:estimates_estimate_changelist")
        response = self.client.get(url, {"q": "EST-ADM-LIST"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EST-ADM-LIST")

    def test_change_form_loads(self):
        url = reverse("admin:estimates_estimate_change", args=[self.estimate.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
