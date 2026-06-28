from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from customers.models import Customer
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"


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


def vehicle_detail_url(pk):
    return reverse("vehicles:detail", kwargs={"pk": pk})


def vehicle_edit_url(pk):
    return reverse("vehicles:edit", kwargs={"pk": pk})


def vehicle_create_url(customer_pk):
    return reverse("customers:vehicle_create", kwargs={"pk": customer_pk})


def customer_detail_url(pk):
    return reverse("customers:detail", kwargs={"pk": pk})


# ---------------------------------------------------------------------------
# Vehicle create for customer
# ---------------------------------------------------------------------------

class VehicleCreateAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()

    def test_login_required(self):
        url = vehicle_create_url(self.customer.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class VehicleCreateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()

    def _valid_data(self, **overrides):
        data = {
            "vin": VALID_VIN,
            "year": 2021,
            "make": "Honda",
            "model": "Civic",
            "trim": "",
            "color": "",
            "license_plate": "",
            "license_state": "",
            "odometer": "",
            "notes": "",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        response = self.client.get(vehicle_create_url(self.customer.pk))
        self.assertEqual(response.status_code, 200)

    def test_form_does_not_expose_customer_field(self):
        response = self.client.get(vehicle_create_url(self.customer.pk))
        self.assertNotContains(response, 'name="customer"')

    def test_valid_post_creates_vehicle_under_url_customer(self):
        self.client.post(vehicle_create_url(self.customer.pk), self._valid_data())
        self.assertTrue(Vehicle.objects.filter(vin=VALID_VIN, customer=self.customer).exists())

    def test_valid_post_redirects_to_customer_detail(self):
        response = self.client.post(vehicle_create_url(self.customer.pk), self._valid_data())
        self.assertRedirects(response, customer_detail_url(self.customer.pk))

    def test_invalid_vin_rerenders_with_errors(self):
        response = self.client.post(vehicle_create_url(self.customer.pk), self._valid_data(vin="BAD"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Vehicle.objects.exists())

    def test_missing_make_rerenders_with_errors(self):
        response = self.client.post(vehicle_create_url(self.customer.pk), self._valid_data(make=""))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Vehicle.objects.exists())


# ---------------------------------------------------------------------------
# Vehicle detail
# ---------------------------------------------------------------------------

class VehicleDetailAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)

    def test_login_required(self):
        url = vehicle_detail_url(self.vehicle.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class VehicleDetailTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer(first_name="Detail", last_name="Test")
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-V-01")

    def test_get_returns_200(self):
        response = self.client.get(vehicle_detail_url(self.vehicle.pk))
        self.assertEqual(response.status_code, 200)

    def test_shows_vin(self):
        response = self.client.get(vehicle_detail_url(self.vehicle.pk))
        self.assertContains(response, VALID_VIN)

    def test_shows_owning_customer(self):
        response = self.client.get(vehicle_detail_url(self.vehicle.pk))
        self.assertContains(response, "Detail Test")

    def test_shows_related_repair_orders(self):
        response = self.client.get(vehicle_detail_url(self.vehicle.pk))
        self.assertContains(response, "RO-V-01")


# ---------------------------------------------------------------------------
# Vehicle edit
# ---------------------------------------------------------------------------

class VehicleEditAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)

    def test_login_required(self):
        url = vehicle_edit_url(self.vehicle.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class VehicleEditTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, color="Red")

    def _valid_data(self, **overrides):
        data = {
            "vin": self.vehicle.vin,
            "year": self.vehicle.year,
            "make": self.vehicle.make,
            "model": self.vehicle.model,
            "trim": "",
            "color": "Red",
            "license_plate": "",
            "license_state": "",
            "odometer": "",
            "notes": "",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        response = self.client.get(vehicle_edit_url(self.vehicle.pk))
        self.assertEqual(response.status_code, 200)

    def test_shows_existing_values(self):
        response = self.client.get(vehicle_edit_url(self.vehicle.pk))
        self.assertContains(response, "Red")

    def test_form_does_not_expose_customer_field(self):
        response = self.client.get(vehicle_edit_url(self.vehicle.pk))
        self.assertNotContains(response, 'name="customer"')

    def test_valid_post_updates_vehicle(self):
        self.client.post(vehicle_edit_url(self.vehicle.pk), self._valid_data(color="Blue"))
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.color, "Blue")

    def test_edit_preserves_existing_customer(self):
        self.client.post(vehicle_edit_url(self.vehicle.pk), self._valid_data())
        self.vehicle.refresh_from_db()
        self.assertEqual(self.vehicle.customer, self.customer)

    def test_valid_post_redirects_to_vehicle_detail(self):
        response = self.client.post(vehicle_edit_url(self.vehicle.pk), self._valid_data())
        self.assertRedirects(response, vehicle_detail_url(self.vehicle.pk))
