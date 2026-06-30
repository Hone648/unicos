from accounts.authorization import ROLE_MANAGER
from customers.models import Customer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"

LIST_URL = reverse("customers:list")
CREATE_URL = reverse("customers:create")


def assign_role(user, role_name):
    group, _created = Group.objects.get_or_create(name=role_name)
    user.groups.add(group)
    return user


def make_user(username="staffer", role_name=ROLE_MANAGER, **kwargs):
    user = get_user_model().objects.create_user(
        username=username, password="pw-test-12345", **kwargs
    )
    if role_name:
        assign_role(user, role_name)
    return user


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


def detail_url(pk):
    return reverse("customers:detail", kwargs={"pk": pk})


def edit_url(pk):
    return reverse("customers:edit", kwargs={"pk": pk})


def vehicle_create_url(customer_pk):
    return reverse("customers:vehicle_create", kwargs={"pk": customer_pk})


# ---------------------------------------------------------------------------
# Customer list
# ---------------------------------------------------------------------------


class CustomerListAuthTests(TestCase):
    def test_login_required(self):
        response = self.client.get(LIST_URL)
        self.assertRedirects(response, f"/accounts/login/?next={LIST_URL}")


class CustomerListTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_get_returns_200(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)

    def test_shows_customers(self):
        make_customer(first_name="Alice", last_name="Brown")
        response = self.client.get(LIST_URL)
        self.assertContains(response, "Alice Brown")

    def test_search_filters_results(self):
        make_customer(first_name="Alice", last_name="Brown")
        make_customer(first_name="Bob", last_name="Jones")
        response = self.client.get(LIST_URL + "?q=Alice")
        self.assertContains(response, "Alice Brown")
        self.assertNotContains(response, "Bob Jones")

    def test_search_no_match_shows_empty_state(self):
        response = self.client.get(LIST_URL + "?q=NOMATCH99999")
        self.assertContains(response, "No customers")


class CustomerListPaginationTests(TestCase):
    """Customer list uses bounded pagination with safe page-parameter handling."""

    PAGE_SIZE = 25

    def setUp(self):
        self.user = make_user(username="cust-paginator")
        self.client.force_login(self.user)
        # Create PAGE_SIZE + 2 customers so two pages exist.
        for i in range(self.PAGE_SIZE + 2):
            Customer.objects.create(
                customer_type=Customer.CustomerType.INDIVIDUAL,
                first_name="Paginate",
                last_name=f"Customer{i:03d}",
            )

    def test_first_page_returns_page_size_results(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["customers"]), self.PAGE_SIZE)

    def test_second_page_returns_remaining_results(self):
        response = self.client.get(LIST_URL + "?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["customers"]), 2)

    def test_invalid_page_falls_back_to_first_page(self):
        response = self.client.get(LIST_URL + "?page=abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["customers"]), self.PAGE_SIZE)

    def test_out_of_range_page_falls_back_to_last_page(self):
        response = self.client.get(LIST_URL + "?page=999")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["customers"]), 2)

    def test_pagination_query_preserves_search_query(self):
        response = self.client.get(LIST_URL + "?q=Paginate")
        self.assertContains(response, "q=Paginate")


# ---------------------------------------------------------------------------
# Customer detail
# ---------------------------------------------------------------------------


class CustomerDetailAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()

    def test_login_required(self):
        url = detail_url(self.customer.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class CustomerDetailTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer(first_name="Carol", last_name="White")
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-C-01")

    def test_get_returns_200(self):
        response = self.client.get(detail_url(self.customer.pk))
        self.assertEqual(response.status_code, 200)

    def test_shows_customer_name(self):
        response = self.client.get(detail_url(self.customer.pk))
        self.assertContains(response, "Carol White")

    def test_shows_related_vehicles(self):
        response = self.client.get(detail_url(self.customer.pk))
        self.assertContains(response, VALID_VIN)

    def test_shows_related_repair_orders(self):
        response = self.client.get(detail_url(self.customer.pk))
        self.assertContains(response, "RO-C-01")


# ---------------------------------------------------------------------------
# Customer create
# ---------------------------------------------------------------------------


class CustomerCreateAuthTests(TestCase):
    def test_login_required(self):
        response = self.client.get(CREATE_URL)
        self.assertRedirects(response, f"/accounts/login/?next={CREATE_URL}")


class CustomerCreateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def _valid_data(self, **overrides):
        data = {
            "customer_type": "individual",
            "first_name": "New",
            "last_name": "Customer",
            "business_name": "",
            "phone_primary": "",
            "phone_secondary": "",
            "email": "",
            "address_line_1": "",
            "address_line_2": "",
            "city": "",
            "state": "",
            "postal_code": "",
            "notes": "",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        response = self.client.get(CREATE_URL)
        self.assertEqual(response.status_code, 200)

    def test_form_does_not_expose_timestamps(self):
        response = self.client.get(CREATE_URL)
        self.assertNotContains(response, 'name="created_at"')
        self.assertNotContains(response, 'name="updated_at"')

    def test_valid_post_creates_customer(self):
        self.client.post(CREATE_URL, self._valid_data())
        self.assertTrue(Customer.objects.filter(first_name="New", last_name="Customer").exists())

    def test_valid_post_redirects_to_detail(self):
        response = self.client.post(CREATE_URL, self._valid_data())
        customer = Customer.objects.get(first_name="New", last_name="Customer")
        self.assertRedirects(response, detail_url(customer.pk))

    def test_invalid_post_rerenders_with_errors(self):
        # Individual with no first or last name is invalid per Customer.clean()
        data = self._valid_data(first_name="", last_name="")
        response = self.client.post(CREATE_URL, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Customer.objects.filter(customer_type="individual").exists())


# ---------------------------------------------------------------------------
# Customer edit
# ---------------------------------------------------------------------------


class CustomerEditAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()

    def test_login_required(self):
        url = edit_url(self.customer.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class CustomerEditTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer(first_name="Edit", last_name="Me", city="Springfield")

    def _valid_data(self, **overrides):
        data = {
            "customer_type": "individual",
            "first_name": self.customer.first_name,
            "last_name": self.customer.last_name,
            "business_name": "",
            "phone_primary": "",
            "phone_secondary": "",
            "email": "",
            "address_line_1": "",
            "address_line_2": "",
            "city": "Springfield",
            "state": "",
            "postal_code": "",
            "notes": "",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        response = self.client.get(edit_url(self.customer.pk))
        self.assertEqual(response.status_code, 200)

    def test_shows_existing_values(self):
        response = self.client.get(edit_url(self.customer.pk))
        self.assertContains(response, "Springfield")

    def test_valid_post_updates_customer(self):
        self.client.post(edit_url(self.customer.pk), self._valid_data(city="Shelbyville"))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.city, "Shelbyville")

    def test_valid_post_redirects_to_detail(self):
        response = self.client.post(edit_url(self.customer.pk), self._valid_data())
        self.assertRedirects(response, detail_url(self.customer.pk))


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


class NavigationTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def test_base_has_customers_nav_link(self):
        response = self.client.get(LIST_URL)
        self.assertContains(response, reverse("customers:list"))

    def test_repair_order_create_has_add_customer_link(self):
        response = self.client.get(reverse("repair_orders:create"))
        self.assertContains(response, reverse("customers:create"))

    def test_repair_order_create_has_open_customers_link(self):
        response = self.client.get(reverse("repair_orders:create"))
        self.assertContains(response, reverse("customers:list"))
