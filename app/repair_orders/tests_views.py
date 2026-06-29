from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.authorization import ROLE_MANAGER, ROLE_TECHNICIAN
from billing.models import Invoice, Payment
from customers.models import Customer
from repair_orders.models import RepairOrder, RepairOrderStatusHistory
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"
VALID_VIN_3 = "5NPE24AF6FH002401"

LIST_URL = reverse("repair_orders:list")
CREATE_URL = reverse("repair_orders:create")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def make_invoice(repair_order, number="INV-001", **kwargs):
    defaults = {"subtotal": Decimal("400.00"), "tax_amount": Decimal("40.00")}
    defaults.update(kwargs)
    return Invoice.objects.create(
        repair_order=repair_order, invoice_number=number, **defaults
    )


def make_payment(invoice, amount=Decimal("100.00"), **kwargs):
    defaults = {"payment_date": date.today(), "method": Payment.Method.CASH}
    defaults.update(kwargs)
    return Payment.objects.create(invoice=invoice, amount=amount, **defaults)


def detail_url(pk):
    return reverse("repair_orders:detail", kwargs={"pk": pk})


def status_url(pk):
    return reverse("repair_orders:status_update", kwargs={"pk": pk})


def edit_url(pk):
    return reverse("repair_orders:edit", kwargs={"pk": pk})


# ---------------------------------------------------------------------------
# List view tests
# ---------------------------------------------------------------------------

class RepairOrderListAuthTests(TestCase):
    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(LIST_URL)
        self.assertRedirects(response, f"/accounts/login/?next={LIST_URL}")

    def test_authenticated_user_can_load_list(self):
        self.client.force_login(make_user())
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)


class RepairOrderListFilterTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)

    def _make_ro(self, number, status=RepairOrder.Status.INTAKE):
        ro = make_repair_order(self.customer, self.vehicle, number=number)
        if status != RepairOrder.Status.INTAKE:
            ro.set_status(status)
        return ro

    def test_list_shows_open_repair_orders_by_default(self):
        ro = self._make_ro("RO-OPEN")
        response = self.client.get(LIST_URL)
        self.assertContains(response, "RO-OPEN")

    def test_list_excludes_closed_by_default(self):
        ro = self._make_ro("RO-CLOSED", RepairOrder.Status.CLOSED)
        response = self.client.get(LIST_URL)
        self.assertNotContains(response, "RO-CLOSED")

    def test_list_excludes_canceled_by_default(self):
        ro = self._make_ro("RO-CANCELED", RepairOrder.Status.CANCELED)
        response = self.client.get(LIST_URL)
        self.assertNotContains(response, "RO-CANCELED")

    def test_status_all_includes_closed(self):
        self._make_ro("RO-CLOSED2", RepairOrder.Status.CLOSED)
        response = self.client.get(LIST_URL + "?status=all")
        self.assertContains(response, "RO-CLOSED2")

    def test_status_closed_shows_only_closed(self):
        self._make_ro("RO-OPEN2")
        self._make_ro("RO-CLOSED3", RepairOrder.Status.CLOSED)
        response = self.client.get(LIST_URL + "?status=closed")
        self.assertNotContains(response, "RO-OPEN2")
        self.assertContains(response, "RO-CLOSED3")

    def test_invalid_status_filter_falls_back_to_open(self):
        self._make_ro("RO-OPEN3")
        self._make_ro("RO-CLOSED4", RepairOrder.Status.CLOSED)
        response = self.client.get(LIST_URL + "?status=bogus")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "RO-OPEN3")
        self.assertNotContains(response, "RO-CLOSED4")


class RepairOrderListSearchTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer(first_name="Alice", last_name="Brown")
        self.vehicle = make_vehicle(
            self.customer, vin=VALID_VIN, license_plate="XYZ999"
        )
        make_repair_order(self.customer, self.vehicle, number="RO-SEARCH-01")

    def test_search_by_repair_order_number(self):
        response = self.client.get(LIST_URL + "?q=RO-SEARCH-01")
        self.assertContains(response, "RO-SEARCH-01")

    def test_search_by_customer_first_name(self):
        response = self.client.get(LIST_URL + "?q=Alice")
        self.assertContains(response, "RO-SEARCH-01")

    def test_search_by_customer_last_name(self):
        response = self.client.get(LIST_URL + "?q=Brown")
        self.assertContains(response, "RO-SEARCH-01")

    def test_search_by_vin(self):
        response = self.client.get(LIST_URL + f"?q={VALID_VIN}")
        self.assertContains(response, "RO-SEARCH-01")

    def test_search_by_license_plate(self):
        response = self.client.get(LIST_URL + "?q=XYZ999")
        self.assertContains(response, "RO-SEARCH-01")

    def test_search_no_match_shows_empty_state(self):
        response = self.client.get(LIST_URL + "?q=NOMATCH99999")
        self.assertContains(response, "No repair orders found")


class RepairOrderListPaginationTests(TestCase):
    """Repair-order list uses bounded pagination with safe page-parameter handling."""

    PAGE_SIZE = 25

    def setUp(self):
        self.user = make_user(username="paginator")
        self.client.force_login(self.user)
        self.customer = make_customer(first_name="Page", last_name="Test")
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN_2)
        # Create PAGE_SIZE + 3 open repair orders so two pages exist.
        for i in range(self.PAGE_SIZE + 3):
            make_repair_order(
                self.customer, self.vehicle, number=f"RO-PAG-{i:03d}"
            )

    def test_first_page_returns_page_size_results(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["repair_orders"]), self.PAGE_SIZE)

    def test_second_page_returns_remaining_results(self):
        response = self.client.get(LIST_URL + "?page=2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["repair_orders"]), 3)

    def test_invalid_page_falls_back_to_first_page(self):
        response = self.client.get(LIST_URL + "?page=abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["repair_orders"]), self.PAGE_SIZE)

    def test_out_of_range_page_falls_back_to_last_page(self):
        response = self.client.get(LIST_URL + "?page=999")
        self.assertEqual(response.status_code, 200)
        # Last page has the 3 overflow items.
        self.assertEqual(len(response.context["repair_orders"]), 3)

    def test_pagination_query_preserves_status_filter(self):
        response = self.client.get(LIST_URL + "?status=all")
        self.assertContains(response, "status=all")

    def test_pagination_query_preserves_search_query(self):
        response = self.client.get(LIST_URL + "?q=RO-PAG")
        # Should still contain search results (all match) and the q param.
        self.assertContains(response, "q=RO-PAG")

    def test_search_results_are_paginated(self):
        response = self.client.get(LIST_URL + "?q=RO-PAG")
        self.assertEqual(response.status_code, 200)
        # All PAGE_SIZE + 3 match "RO-PAG", first page caps at PAGE_SIZE.
        self.assertEqual(len(response.context["repair_orders"]), self.PAGE_SIZE)


# ---------------------------------------------------------------------------
# Detail view tests
# ---------------------------------------------------------------------------

class RepairOrderDetailAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_unauthenticated_redirects_to_login(self):
        url = detail_url(self.ro.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")

    def test_authenticated_user_can_load_detail(self):
        self.client.force_login(make_user())
        response = self.client.get(detail_url(self.ro.pk))
        self.assertEqual(response.status_code, 200)


class RepairOrderDetailContentTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer(first_name="Bob", last_name="Jones")
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(
            self.customer, self.vehicle,
            number="RO-DETAIL-01",
            reported_problem="Bumper crack",
        )

    def test_detail_shows_repair_order_number(self):
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, "RO-DETAIL-01")

    def test_detail_heading_has_no_duplicated_ro_prefix(self):
        ro = make_repair_order(self.customer, self.vehicle, number="RO-2099-000001")
        response = self.client.get(detail_url(ro.pk))
        self.assertContains(response, "Repair Order RO-2099-000001")
        self.assertNotContains(response, "RO RO-2099-000001")

    def test_detail_shows_customer_name(self):
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, "Bob")

    def test_detail_shows_status_history(self):
        response = self.client.get(detail_url(self.ro.pk))
        # Initial intake history row is always created on save
        self.assertContains(response, "Intake")

    def test_detail_shows_invoice_summary_when_invoice_exists(self):
        make_invoice(self.ro, number="INV-DETAIL-01")
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, "INV-DETAIL-01")
        self.assertContains(response, "440.00")  # total_amount

    def test_detail_has_no_invoice_section_when_no_invoice(self):
        response = self.client.get(detail_url(self.ro.pk))
        self.assertNotContains(response, "INV-")

    def test_404_for_nonexistent_repair_order(self):
        response = self.client.get(detail_url(99999))
        self.assertEqual(response.status_code, 404)


class FinalRepairOrderDetailTests(TestCase):
    def setUp(self):
        self.user = make_user(username="final_detail_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(
            self.customer,
            self.vehicle,
            number="RO-FINAL-DETAIL",
            reported_problem="Final order remains visible",
        )

    def _set_status(self, status):
        # Use _apply_status_change to bypass lifecycle rules for test setup;
        # these tests exercise detail-page rendering, not the transition itself.
        self.ro._apply_status_change(status, changed_by=self.user, note="Final status for test")
        self.ro.refresh_from_db()

    def test_delivered_detail_does_not_show_edit_repair_order_link(self):
        self._set_status(RepairOrder.Status.DELIVERED)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertNotContains(response, edit_url(self.ro.pk))
        self.assertNotContains(response, "Edit Repair Order")

    def test_closed_detail_does_not_show_edit_repair_order_link(self):
        self._set_status(RepairOrder.Status.CLOSED)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertNotContains(response, edit_url(self.ro.pk))
        self.assertNotContains(response, "Edit Repair Order")

    def test_canceled_detail_does_not_show_edit_repair_order_link(self):
        self._set_status(RepairOrder.Status.CANCELED)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertNotContains(response, edit_url(self.ro.pk))
        self.assertNotContains(response, "Edit Repair Order")

    def test_final_detail_still_shows_repair_order_number(self):
        self._set_status(RepairOrder.Status.DELIVERED)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, "RO-FINAL-DETAIL")

    def test_final_detail_still_shows_status_history(self):
        self._set_status(RepairOrder.Status.DELIVERED)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, "Status History")
        self.assertContains(response, "Delivered")

    def test_final_detail_still_shows_invoice_summary_when_invoice_exists(self):
        make_invoice(self.ro, number="INV-FINAL-DETAIL")
        self._set_status(RepairOrder.Status.DELIVERED)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, "Invoice")
        self.assertContains(response, "INV-FINAL-DETAIL")


# ---------------------------------------------------------------------------
# Status update view tests
# ---------------------------------------------------------------------------

class RepairOrderStatusUpdateAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_unauthenticated_redirects_to_login(self):
        url = status_url(self.ro.pk)
        response = self.client.post(url, {"new_status": "estimating"})
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class RepairOrderStatusUpdateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-STATUS-01")

    def test_post_changes_status(self):
        self.client.post(status_url(self.ro.pk), {"new_status": "estimating"})
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.ESTIMATING)

    def test_post_creates_history_with_changed_by(self):
        history_count_before = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self.client.post(status_url(self.ro.pk), {"new_status": "estimating"})
        entries = RepairOrderStatusHistory.objects.filter(repair_order=self.ro)
        self.assertEqual(entries.count(), history_count_before + 1)
        latest = entries.order_by("-changed_at").first()
        self.assertEqual(latest.changed_by, self.user)
        self.assertEqual(latest.new_status, RepairOrder.Status.ESTIMATING)

    def test_post_redirects_to_detail(self):
        response = self.client.post(
            status_url(self.ro.pk), {"new_status": "estimating"}
        )
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_same_status_does_not_create_duplicate_history(self):
        # RO starts at INTAKE — posting INTAKE again should be a no-op
        history_count_before = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self.client.post(status_url(self.ro.pk), {"new_status": "intake"})
        self.assertEqual(
            RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count(),
            history_count_before,
        )

    def test_invalid_status_does_not_mutate_repair_order(self):
        original_status = self.ro.status
        self.client.post(status_url(self.ro.pk), {"new_status": "not_a_real_status"})
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, original_status)

    def test_invalid_status_redirects_to_detail(self):
        response = self.client.post(
            status_url(self.ro.pk), {"new_status": "not_a_real_status"}
        )
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_get_to_status_update_url_redirects_to_detail(self):
        response = self.client.get(status_url(self.ro.pk))
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_default_note_applied_when_note_blank(self):
        self.client.post(
            status_url(self.ro.pk), {"new_status": "estimating", "note": ""}
        )
        latest = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).order_by("-changed_at").first()
        self.assertEqual(latest.note, "Status changed from repair order workspace.")

    def test_custom_note_is_preserved(self):
        self.client.post(
            status_url(self.ro.pk),
            {"new_status": "estimating", "note": "Customer approved estimate"},
        )
        latest = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).order_by("-changed_at").first()
        self.assertEqual(latest.note, "Customer approved estimate")


# ---------------------------------------------------------------------------
# HTMX status update tests
# ---------------------------------------------------------------------------

class RepairOrderStatusUpdateHTMXTests(TestCase):
    def setUp(self):
        self.user = make_user(username="htmx_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN_2)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-HTMX-01")

    def _htmx_post(self, data):
        return self.client.post(
            status_url(self.ro.pk),
            data,
            HTTP_HX_REQUEST="true",
        )

    def test_htmx_post_valid_status_returns_200_not_redirect(self):
        response = self._htmx_post({"new_status": "estimating"})
        self.assertEqual(response.status_code, 200)

    def test_htmx_post_valid_status_mutates_repair_order(self):
        self._htmx_post({"new_status": "estimating"})
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.ESTIMATING)

    def test_htmx_post_valid_status_creates_history_with_changed_by(self):
        count_before = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self._htmx_post({"new_status": "estimating"})
        entries = RepairOrderStatusHistory.objects.filter(repair_order=self.ro)
        self.assertEqual(entries.count(), count_before + 1)
        latest = entries.order_by("-changed_at").first()
        self.assertEqual(latest.changed_by, self.user)
        self.assertEqual(latest.new_status, RepairOrder.Status.ESTIMATING)

    def test_htmx_post_response_contains_updated_status_text(self):
        response = self._htmx_post({"new_status": "estimating"})
        self.assertContains(response, "Estimating")

    def test_htmx_post_response_contains_status_history_section(self):
        response = self._htmx_post({"new_status": "estimating"})
        self.assertContains(response, "Status History")

    def test_htmx_post_same_status_does_not_create_duplicate_history(self):
        # RO starts at INTAKE — posting INTAKE again is a no-op
        count_before = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self._htmx_post({"new_status": "intake"})
        self.assertEqual(
            RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count(),
            count_before,
        )

    def test_htmx_post_invalid_status_does_not_mutate_repair_order(self):
        original_status = self.ro.status
        self._htmx_post({"new_status": "not_a_real_status"})
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, original_status)

    def test_htmx_post_invalid_status_returns_response_with_error_message(self):
        response = self._htmx_post({"new_status": "not_a_real_status"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not a valid repair order status")

    def test_non_htmx_post_still_redirects(self):
        response = self.client.post(
            status_url(self.ro.pk), {"new_status": "estimating"}
        )
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_non_htmx_post_still_updates_status(self):
        self.client.post(status_url(self.ro.pk), {"new_status": "estimating"})
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.ESTIMATING)


# ---------------------------------------------------------------------------
# Create view tests
# ---------------------------------------------------------------------------

class RepairOrderCreateAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(CREATE_URL)
        self.assertRedirects(response, f"/accounts/login/?next={CREATE_URL}")


class RepairOrderCreateTests(TestCase):
    def setUp(self):
        self.user = make_user(username="create_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN)
        # Second customer + vehicle for mismatch tests
        self.other_customer = make_customer(first_name="Other", last_name="Person")
        self.other_vehicle = make_vehicle(self.other_customer, vin=VALID_VIN_3)

    def _valid_post_data(self, **overrides):
        data = {
            "customer": self.customer.pk,
            "vehicle": self.vehicle.pk,
        }
        data.update(overrides)
        return data

    def test_create_get_returns_200(self):
        response = self.client.get(CREATE_URL)
        self.assertEqual(response.status_code, 200)

    def test_create_page_contains_form_fields(self):
        response = self.client.get(CREATE_URL)
        self.assertNotContains(response, 'name="repair_order_number"')
        self.assertContains(response, 'name="customer"')
        self.assertContains(response, 'name="vehicle"')

    def test_create_form_does_not_expose_status_field(self):
        response = self.client.get(CREATE_URL)
        self.assertNotContains(response, 'name="status"')

    def test_valid_post_creates_repair_order(self):
        count_before = RepairOrder.objects.count()
        self.client.post(CREATE_URL, self._valid_post_data())
        self.assertEqual(RepairOrder.objects.count(), count_before + 1)

    def test_valid_post_auto_generates_repair_order_number(self):
        self.client.post(CREATE_URL, self._valid_post_data())
        ro = RepairOrder.objects.get(customer=self.customer)
        self.assertRegex(ro.repair_order_number, r"^RO-\d{4}-\d{6}$")

    def test_valid_post_redirects_to_detail(self):
        response = self.client.post(CREATE_URL, self._valid_post_data())
        ro = RepairOrder.objects.get(customer=self.customer)
        self.assertRedirects(response, detail_url(ro.pk))

    def test_valid_post_sets_created_by(self):
        self.client.post(CREATE_URL, self._valid_post_data())
        ro = RepairOrder.objects.get(customer=self.customer)
        self.assertEqual(ro.created_by, self.user)

    def test_valid_post_sets_updated_by(self):
        self.client.post(CREATE_URL, self._valid_post_data())
        ro = RepairOrder.objects.get(customer=self.customer)
        self.assertEqual(ro.updated_by, self.user)

    def test_created_repair_order_starts_with_default_status(self):
        self.client.post(CREATE_URL, self._valid_post_data())
        ro = RepairOrder.objects.get(customer=self.customer)
        self.assertEqual(ro.status, RepairOrder.Status.INTAKE)

    def test_customer_vehicle_mismatch_does_not_create_repair_order(self):
        count_before = RepairOrder.objects.count()
        self.client.post(CREATE_URL, self._valid_post_data(
            vehicle=self.other_vehicle.pk,
        ))
        self.assertEqual(RepairOrder.objects.count(), count_before)

    def test_customer_vehicle_mismatch_displays_form_error(self):
        response = self.client.post(CREATE_URL, self._valid_post_data(
            vehicle=self.other_vehicle.pk,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not belong to the selected customer")


# ---------------------------------------------------------------------------
# Edit view tests
# ---------------------------------------------------------------------------

class RepairOrderEditAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-EDIT-AUTH")

    def test_unauthenticated_redirects_to_login(self):
        url = edit_url(self.ro.pk)
        response = self.client.get(url)
        self.assertRedirects(response, f"/accounts/login/?next={url}")


class RepairOrderEditTests(TestCase):
    def setUp(self):
        self.user = make_user(username="edit_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN)
        self.ro = make_repair_order(
            self.customer, self.vehicle,
            number="RO-EDIT-01",
            reported_problem="Original problem",
        )
        # Second customer + vehicle for mismatch tests
        self.other_customer = make_customer(first_name="Other", last_name="Person")
        self.other_vehicle = make_vehicle(self.other_customer, vin=VALID_VIN_3)

    def _valid_post_data(self, **overrides):
        data = {
            "customer": self.customer.pk,
            "vehicle": self.vehicle.pk,
            "reported_problem": "Updated problem",
        }
        data.update(overrides)
        return data

    def test_edit_get_returns_200(self):
        response = self.client.get(edit_url(self.ro.pk))
        self.assertEqual(response.status_code, 200)

    def test_edit_page_contains_existing_values(self):
        response = self.client.get(edit_url(self.ro.pk))
        self.assertContains(response, "RO-EDIT-01")
        self.assertContains(response, "Original problem")

    def test_edit_form_does_not_expose_status_field(self):
        response = self.client.get(edit_url(self.ro.pk))
        self.assertNotContains(response, 'name="status"')

    def test_valid_edit_post_updates_fields(self):
        self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.reported_problem, "Updated problem")

    def test_valid_edit_post_redirects_to_detail(self):
        response = self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_valid_edit_post_sets_updated_by(self):
        self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.updated_by, self.user)

    def test_edit_does_not_create_status_history_for_basic_field_changes(self):
        count_before = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        count_after = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self.assertEqual(count_before, count_after)

    def test_customer_vehicle_mismatch_does_not_update_repair_order(self):
        self.client.post(edit_url(self.ro.pk), self._valid_post_data(
            vehicle=self.other_vehicle.pk,
        ))
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.reported_problem, "Original problem")

    def test_customer_vehicle_mismatch_displays_form_error(self):
        response = self.client.post(edit_url(self.ro.pk), self._valid_post_data(
            vehicle=self.other_vehicle.pk,
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "does not belong to the selected customer")

    def test_edit_form_does_not_expose_editable_ro_number(self):
        response = self.client.get(edit_url(self.ro.pk))
        self.assertNotContains(response, 'name="repair_order_number"')

    def test_edit_preserves_existing_repair_order_number(self):
        original_number = self.ro.repair_order_number
        self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.repair_order_number, original_number)


class FinalRepairOrderEditGuardTests(TestCase):
    def setUp(self):
        self.user = make_user(username="final_edit_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(
            self.customer,
            self.vehicle,
            number="RO-FINAL-EDIT",
            reported_problem="Original final problem",
            internal_notes="Original final notes",
        )

    def _valid_post_data(self, **overrides):
        data = {
            "customer": self.customer.pk,
            "vehicle": self.vehicle.pk,
            "reported_problem": "Changed final problem",
            "internal_notes": "Changed final notes",
        }
        data.update(overrides)
        return data

    def _set_status(self, status):
        self.ro.set_status(status, changed_by=self.user, note="Final status for test")
        self.ro.refresh_from_db()

    def test_delivered_repair_order_edit_get_redirects_to_detail(self):
        self._set_status(RepairOrder.Status.DELIVERED)
        response = self.client.get(edit_url(self.ro.pk))
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_delivered_repair_order_edit_get_shows_error_message(self):
        self._set_status(RepairOrder.Status.DELIVERED)
        response = self.client.get(edit_url(self.ro.pk), follow=True)
        self.assertContains(
            response,
            "Repair order RO-FINAL-EDIT is final and cannot be edited.",
        )

    def test_delivered_repair_order_edit_post_redirects_to_detail(self):
        self._set_status(RepairOrder.Status.DELIVERED)
        response = self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_delivered_repair_order_edit_post_does_not_change_fields(self):
        self._set_status(RepairOrder.Status.DELIVERED)
        self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.reported_problem, "Original final problem")
        self.assertEqual(self.ro.internal_notes, "Original final notes")

    def test_delivered_repair_order_edit_post_does_not_create_status_history_row(self):
        self._set_status(RepairOrder.Status.DELIVERED)
        count_before = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        count_after = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self.assertEqual(count_before, count_after)

    def test_closed_repair_order_edit_get_redirects_to_detail(self):
        self._set_status(RepairOrder.Status.CLOSED)
        response = self.client.get(edit_url(self.ro.pk))
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_canceled_repair_order_edit_get_redirects_to_detail(self):
        self._set_status(RepairOrder.Status.CANCELED)
        response = self.client.get(edit_url(self.ro.pk))
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_non_final_repair_order_edit_get_still_returns_200(self):
        self._set_status(RepairOrder.Status.QUALITY_CHECK)
        response = self.client.get(edit_url(self.ro.pk))
        self.assertEqual(response.status_code, 200)

    def test_non_final_repair_order_edit_post_still_updates_fields(self):
        self._set_status(RepairOrder.Status.QUALITY_CHECK)
        self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.reported_problem, "Changed final problem")

    def test_non_final_repair_order_detail_still_shows_edit_link(self):
        self._set_status(RepairOrder.Status.QUALITY_CHECK)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, edit_url(self.ro.pk))
        self.assertContains(response, "Edit Repair Order")


# ---------------------------------------------------------------------------
# Navigation link tests
# ---------------------------------------------------------------------------

class RepairOrderNavigationTests(TestCase):
    def setUp(self):
        self.user = make_user(username="nav_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN_2)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-NAV-01")

    def test_list_page_contains_create_link(self):
        response = self.client.get(LIST_URL)
        self.assertContains(response, CREATE_URL)

    def test_detail_page_contains_edit_link(self):
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, edit_url(self.ro.pk))


# ---------------------------------------------------------------------------
# Closure rule tests (non-HTMX)
# ---------------------------------------------------------------------------

class RepairOrderClosureRuleTests(TestCase):
    """Final-status transitions are blocked when a non-void invoice has balance due."""

    def setUp(self):
        self.user = make_user(username="closure_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN_3)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-CLOSURE-01")
        # Draft invoice, total = 440, nothing paid → balance_due = 440
        self.invoice = make_invoice(self.ro, number="INV-CLOSURE-01")

    def _post_status(self, new_status, note=""):
        return self.client.post(
            status_url(self.ro.pk),
            {"new_status": new_status, "note": note},
        )

    # --- blocking behavior ---

    def test_cannot_transition_to_delivered_with_balance_due(self):
        response = self._post_status("delivered")
        self.ro.refresh_from_db()
        self.assertNotEqual(self.ro.status, RepairOrder.Status.DELIVERED)

    def test_cannot_transition_to_closed_with_balance_due(self):
        self._post_status("closed")
        self.ro.refresh_from_db()
        self.assertNotEqual(self.ro.status, RepairOrder.Status.CLOSED)

    def test_cannot_transition_to_canceled_with_balance_due(self):
        self._post_status("canceled")
        self.ro.refresh_from_db()
        self.assertNotEqual(self.ro.status, RepairOrder.Status.CANCELED)

    def test_blocked_transition_leaves_status_unchanged(self):
        original_status = self.ro.status
        self._post_status("delivered")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, original_status)

    def test_blocked_transition_does_not_create_history(self):
        count_before = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self._post_status("delivered")
        count_after = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self.assertEqual(count_before, count_after)

    def test_blocked_transition_redirects_to_detail(self):
        response = self._post_status("delivered")
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_partially_paid_invoice_with_balance_blocks_final_status(self):
        # Pay half the invoice — balance_due is still > 0
        make_payment(self.invoice, Decimal("100.00"))
        self._post_status("delivered")
        self.ro.refresh_from_db()
        self.assertNotEqual(self.ro.status, RepairOrder.Status.DELIVERED)

    # --- allowed behavior ---

    def test_can_transition_to_delivered_with_no_invoice(self):
        ro = make_repair_order(self.customer, self.vehicle, number="RO-NO-INV")
        self.client.post(status_url(ro.pk), {"new_status": "delivered"})
        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.DELIVERED)

    def test_can_transition_to_delivered_with_void_invoice(self):
        self.invoice.status = Invoice.Status.VOID
        self.invoice.save(update_fields=["status", "updated_at"])
        self._post_status("delivered")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.DELIVERED)

    def test_can_transition_to_delivered_with_fully_paid_invoice(self):
        # Invoice total = 440; pay full amount
        make_payment(self.invoice, Decimal("440.00"))
        self._post_status("delivered")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.DELIVERED)

    def test_can_transition_to_non_final_status_with_balance_due(self):
        self._post_status("in_repair")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.IN_REPAIR)

    def test_non_final_transition_still_creates_history(self):
        count_before = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self._post_status("in_repair")
        count_after = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self.assertEqual(count_after, count_before + 1)

    def test_delivered_to_closed_still_succeeds_when_invoice_rule_allows_it(self):
        ro = make_repair_order(self.customer, self.vehicle, number="RO-DELIV-CLOSE")
        ro.set_status(RepairOrder.Status.DELIVERED, changed_by=self.user)
        response = self.client.post(status_url(ro.pk), {"new_status": "closed"})
        self.assertRedirects(response, detail_url(ro.pk))
        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.CLOSED)

    def test_final_repair_order_status_history_remains_visible(self):
        ro = make_repair_order(self.customer, self.vehicle, number="RO-FINAL-HISTORY")
        ro.set_status(RepairOrder.Status.DELIVERED, changed_by=self.user)
        response = self.client.get(detail_url(ro.pk))
        self.assertContains(response, "Status History")
        self.assertContains(response, "Delivered")


# ---------------------------------------------------------------------------
# Closure rule HTMX tests
# ---------------------------------------------------------------------------

class RepairOrderClosureRuleHTMXTests(TestCase):
    def setUp(self):
        self.user = make_user(username="closure_htmx_user")
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN_2)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-CLOSURE-HX")
        # Draft invoice with balance due
        self.invoice = make_invoice(self.ro, number="INV-CLOSURE-HX")

    def _htmx_post(self, new_status):
        return self.client.post(
            status_url(self.ro.pk),
            {"new_status": new_status},
            HTTP_HX_REQUEST="true",
        )

    def test_htmx_blocked_transition_returns_200(self):
        response = self._htmx_post("delivered")
        self.assertEqual(response.status_code, 200)

    def test_htmx_blocked_transition_includes_error_message(self):
        response = self._htmx_post("delivered")
        self.assertContains(response, "balance due")

    def test_htmx_blocked_transition_leaves_status_unchanged(self):
        original_status = self.ro.status
        self._htmx_post("delivered")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, original_status)

    def test_htmx_blocked_transition_does_not_create_history(self):
        count_before = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self._htmx_post("delivered")
        count_after = RepairOrderStatusHistory.objects.filter(
            repair_order=self.ro
        ).count()
        self.assertEqual(count_before, count_after)

    def test_htmx_allowed_transition_still_updates_status(self):
        self._htmx_post("in_repair")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.IN_REPAIR)

    def test_htmx_paid_invoice_allows_final_status(self):
        make_payment(self.invoice, Decimal("440.00"))
        self._htmx_post("delivered")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.DELIVERED)


# ---------------------------------------------------------------------------
# Invoice summary billing permission tests
# ---------------------------------------------------------------------------

class InvoiceSummaryPermissionTests(TestCase):
    """RO detail invoice card: billing.view gate; Technician sees neutral message."""

    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle, number="RO-INV-PERM-01")
        self.invoice = make_invoice(self.ro, number="INV-PERM-001")

    def _login(self, username, role_name):
        user = make_user(username=username, role_name=role_name)
        self.client.force_login(user)

    def test_technician_can_load_ro_detail(self):
        self._login("tech-ro-load", ROLE_TECHNICIAN)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertEqual(response.status_code, 200)

    def test_technician_sees_neutral_invoice_message(self):
        self._login("tech-ro-neutral", ROLE_TECHNICIAN)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, "Invoice details require billing permission.")

    def test_technician_does_not_see_invoice_number(self):
        self._login("tech-ro-no-num", ROLE_TECHNICIAN)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertNotContains(response, "INV-PERM-001")

    def test_technician_does_not_see_balance_due_label(self):
        self._login("tech-ro-no-bal", ROLE_TECHNICIAN)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertNotContains(response, "Balance due")

    def test_technician_does_not_see_view_print_invoice_link(self):
        self._login("tech-ro-no-link", ROLE_TECHNICIAN)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertNotContains(response, "View/Print Invoice")

    def test_manager_sees_invoice_summary(self):
        self._login("mgr-ro-sees", ROLE_MANAGER)
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, "INV-PERM-001")
        self.assertContains(response, "View/Print Invoice")
        self.assertNotContains(response, "Invoice details require billing permission.")
