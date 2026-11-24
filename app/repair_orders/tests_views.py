import re
from datetime import date
from decimal import Decimal
from html import unescape
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from accounts.authorization import (
    PERM_CUSTOMERS_VIEW,
    PERM_REPAIR_ORDERS_CHANGE_STATUS,
    PERM_REPAIR_ORDERS_MANAGE,
    PERM_REPAIR_ORDERS_VIEW,
    ROLE_ESTIMATOR,
    ROLE_FRONT_DESK,
    ROLE_MANAGER,
    ROLE_PERMISSION_MATRIX,
    ROLE_READ_ONLY,
    ROLE_TECHNICIAN,
)
from billing.models import Invoice, Payment
from customers.models import Customer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from repair_orders.models import RepairOrder, RepairOrderStatusHistory
from repair_orders.status_continuation import sign_status_continuation
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"
VALID_VIN_3 = "5NPE24AF6FH002401"

LIST_URL = reverse("repair_orders:list")
CREATE_URL = reverse("repair_orders:create")
VEHICLE_FIELD_URL = reverse("repair_orders:vehicle_field")


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
    return Invoice.objects.create(repair_order=repair_order, invoice_number=number, **defaults)


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


class RepairOrderObjectPolicyViewTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.other_vehicle = make_vehicle(self.customer, vin=VALID_VIN_2)
        self.technician = make_user(username="ro-policy-tech", role_name=ROLE_TECHNICIAN)
        self.assigned_ro = make_repair_order(
            self.customer,
            self.vehicle,
            number="RO-POLICY-ASSIGNED",
            assigned_to=self.technician,
        )
        self.unassigned_ro = make_repair_order(
            self.customer,
            self.other_vehicle,
            number="RO-POLICY-UNASSIGNED",
        )

    def test_technician_can_open_assigned_repair_order_detail(self):
        self.client.force_login(self.technician)
        response = self.client.get(detail_url(self.assigned_ro.pk))
        self.assertEqual(response.status_code, 200)

    def test_technician_gets_403_for_unassigned_repair_order_detail(self):
        self.client.force_login(self.technician)
        response = self.client.get(detail_url(self.unassigned_ro.pk))
        self.assertEqual(response.status_code, 403)

    def test_technician_list_only_includes_assigned_repair_orders(self):
        self.client.force_login(self.technician)
        response = self.client.get(LIST_URL)
        self.assertContains(response, "RO-POLICY-ASSIGNED")
        self.assertNotContains(response, "RO-POLICY-UNASSIGNED")

    def test_read_only_can_view_but_cannot_post_mutation_endpoint(self):
        user = make_user(username="ro-policy-readonly", role_name=ROLE_READ_ONLY)
        self.client.force_login(user)
        self.assertEqual(self.client.get(detail_url(self.unassigned_ro.pk)).status_code, 200)
        response = self.client.post(
            edit_url(self.unassigned_ro.pk),
            {
                "customer": self.customer.pk,
                "vehicle": self.other_vehicle.pk,
                "assigned_to": "",
                "promised_date": "",
                "reported_problem": "No save",
                "internal_notes": "",
            },
        )
        self.assertEqual(response.status_code, 403)


class RepairOrderListFilterTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)

    def _make_ro(self, number, status=RepairOrder.Status.INTAKE):
        ro = make_repair_order(self.customer, self.vehicle, number=number)
        if status != RepairOrder.Status.INTAKE:
            ro._apply_status_change(status)
        return ro

    def test_list_shows_open_repair_orders_by_default(self):
        self._make_ro("RO-OPEN")
        response = self.client.get(LIST_URL)
        self.assertContains(response, "RO-OPEN")

    def test_list_excludes_closed_by_default(self):
        self._make_ro("RO-CLOSED", RepairOrder.Status.CLOSED)
        response = self.client.get(LIST_URL)
        self.assertNotContains(response, "RO-CLOSED")

    def test_list_excludes_canceled_by_default(self):
        self._make_ro("RO-CANCELED", RepairOrder.Status.CANCELED)
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
        self.vehicle = make_vehicle(self.customer, vin=VALID_VIN, license_plate="XYZ999")
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
            make_repair_order(self.customer, self.vehicle, number=f"RO-PAG-{i:03d}")

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
            self.customer,
            self.vehicle,
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

    def test_detail_loads_pinned_htmx_script(self):
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(
            response,
            '<script src="https://unpkg.com/htmx.org@2.0.4" defer></script>',
            html=True,
        )

    def test_detail_preserves_status_form_htmx_attributes(self):
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, 'id="status-update-card"')
        self.assertContains(response, f'action="{status_url(self.ro.pk)}"')
        self.assertContains(response, f'hx-post="{status_url(self.ro.pk)}"')
        self.assertContains(response, 'hx-target="#status-update-card"')
        self.assertContains(response, 'hx-swap="outerHTML"')

    def test_detail_shows_invoice_summary_when_invoice_exists(self):
        make_invoice(self.ro, number="INV-DETAIL-01")
        response = self.client.get(detail_url(self.ro.pk))
        self.assertContains(response, "INV-DETAIL-01")
        self.assertContains(response, "440.00")  # total_amount

    def test_detail_has_no_invoice_section_when_no_invoice(self):
        response = self.client.get(detail_url(self.ro.pk))
        self.assertNotContains(response, "INV-")

    def test_detail_groups_records_in_reading_order_without_repeating_problem(self):
        self.ro.internal_notes = "Call before additional repairs."
        self.ro.save()
        make_invoice(self.ro, number="INV-LAYOUT")
        response = self.client.get(detail_url(self.ro.pk))
        content = response.content.decode()
        self.assertEqual(
            [unescape(heading) for heading in re.findall(r"<h2[^>]*>(.*?)</h2>", content)],
            ["Overview", "Status & next action", "Estimate & invoice", "Activity & files"],
        )
        self.assertContains(response, "Bumper crack", count=1)
        overview = content.split('id="job-overview-heading"')[1].split("</section>")[0]
        activity = content.split('id="job-activity-heading"')[1].split("</section>")[0]
        billing = content.split('id="job-billing-heading"')[1].split("</section>")[0]
        self.assertIn("Bumper crack", overview)
        self.assertIn(VALID_VIN, overview)
        self.assertNotIn("Call before additional repairs.", overview)
        self.assertIn("Call before additional repairs.", activity)
        self.assertLess(billing.index("<h3>Estimates</h3>"), billing.index("<h3>Invoice</h3>"))
        self.assertIn("INV-LAYOUT", billing)

    def test_history_disclosure_is_outside_the_htmx_replacement_region(self):
        detail = self.client.get(detail_url(self.ro.pk))
        self.assertRegex(
            detail.content.decode(),
            re.compile(
                r'<details class="ro-history">\s*<summary>Status History</summary>'
                r'\s*<div id="status-history-card" hx-swap-oob="true">.*?</div>\s*</details>',
                re.S,
            ),
        )
        response = self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": RepairOrder.Status.ESTIMATING,
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, 'id="status-history-card" hx-swap-oob="true"', count=1)
        self.assertNotContains(response, '<details class="ro-history">')
        self.assertNotContains(response, "<summary>Status History</summary>")
        self.assertContains(response, "<td>Estimating</td>", html=True)

    def test_blocked_closure_prioritizes_payment_and_preserves_status_target(self):
        self.ro._apply_status_change(RepairOrder.Status.READY_FOR_PICKUP)
        make_invoice(self.ro)
        response = self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": RepairOrder.Status.DELIVERED,
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertContains(response, 'id="status-balance-warning"')
        self.assertContains(response, 'aria-describedby="status-payment-hint"')
        self.assertContains(response, '<a class="btn btn-primary"', count=1)
        self.assertContains(
            response,
            '<button class="btn btn-outline-secondary" type="submit">Update Status</button>',
            html=True,
        )
        self.assertContains(
            response, '<option value="delivered" selected>Delivered</option>', html=True
        )
        self.assertContains(response, 'hx-target="#status-update-card"')
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.READY_FOR_PICKUP)

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
        self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": "estimating",
            },
        )
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.ESTIMATING)

    def test_post_creates_history_with_changed_by(self):
        history_count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": "estimating",
            },
        )
        entries = RepairOrderStatusHistory.objects.filter(repair_order=self.ro)
        self.assertEqual(entries.count(), history_count_before + 1)
        latest = entries.order_by("-changed_at").first()
        self.assertEqual(latest.changed_by, self.user)
        self.assertEqual(latest.new_status, RepairOrder.Status.ESTIMATING)

    def test_post_redirects_to_detail(self):
        response = self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": "estimating",
            },
        )
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_same_status_does_not_create_duplicate_history(self):
        # RO starts at INTAKE — posting INTAKE again should be a no-op
        history_count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": "intake",
            },
        )
        self.assertEqual(
            RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count(),
            history_count_before,
        )

    def test_invalid_status_does_not_mutate_repair_order(self):
        original_status = self.ro.status
        self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": "not_a_real_status",
            },
        )
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, original_status)

    def test_invalid_status_redirects_to_detail(self):
        response = self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": "not_a_real_status",
            },
        )
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_get_to_status_update_url_redirects_to_detail(self):
        response = self.client.get(status_url(self.ro.pk))
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_default_note_applied_when_note_blank(self):
        self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": "estimating",
                "note": "",
            },
        )
        latest = (
            RepairOrderStatusHistory.objects.filter(repair_order=self.ro)
            .order_by("-changed_at")
            .first()
        )
        self.assertEqual(latest.note, "Status changed from repair order workspace.")

    def test_custom_note_is_preserved(self):
        self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": "estimating",
                "note": "Customer approved estimate",
            },
        )
        latest = (
            RepairOrderStatusHistory.objects.filter(repair_order=self.ro)
            .order_by("-changed_at")
            .first()
        )
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
            {"expected_status": self.ro.status, **data},
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
        count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
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

    def test_htmx_post_response_contains_oob_swap_fragments(self):
        response = self._htmx_post({"new_status": "estimating"})
        self.assertContains(response, 'id="messages" class="messages" hx-swap-oob="true"')
        self.assertContains(response, 'id="ro-status-badge"')
        self.assertContains(response, 'hx-swap-oob="true"')
        self.assertContains(response, 'id="status-history-card"')
        self.assertContains(response, 'id="status-update-card"')
        self.assertContains(response, f'hx-post="{status_url(self.ro.pk)}"')
        self.assertContains(response, 'hx-target="#status-update-card"')

    def test_htmx_post_same_status_does_not_create_duplicate_history(self):
        # RO starts at INTAKE — posting INTAKE again is a no-op
        count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
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
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": "estimating",
            },
        )
        self.assertRedirects(response, detail_url(self.ro.pk))

    def test_non_htmx_post_still_updates_status(self):
        self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": "estimating",
            },
        )
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

    def test_create_get_vehicle_select_starts_disabled_until_customer_selected(self):
        response = self.client.get(CREATE_URL)

        self.assertContains(response, "Select a customer first")
        self.assertContains(response, "disabled")
        self.assertContains(response, "Select a customer to load that customer's vehicles.")
        self.assertNotContains(response, VALID_VIN)
        self.assertNotContains(response, VALID_VIN_3)

    def test_create_customer_select_loads_vehicle_field_with_htmx(self):
        response = self.client.get(CREATE_URL)

        self.assertContains(response, f'hx-get="{VEHICLE_FIELD_URL}"')
        self.assertContains(response, 'hx-target="#vehicle-field"')
        self.assertContains(response, 'hx-trigger="change"')

    def test_vehicle_field_partial_filters_vehicles_to_selected_customer(self):
        response = self.client.get(VEHICLE_FIELD_URL, {"customer": self.customer.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a vehicle")
        self.assertContains(response, VALID_VIN)
        self.assertNotContains(response, VALID_VIN_3)
        self.assertNotContains(response, "disabled")

    def test_vehicle_field_partial_disables_select_when_customer_has_no_vehicles(self):
        empty_customer = make_customer(first_name="No", last_name="Vehicles")

        response = self.client.get(VEHICLE_FIELD_URL, {"customer": empty_customer.pk})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No vehicles found for this customer")
        self.assertContains(response, "disabled")

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
        self.client.post(
            CREATE_URL,
            self._valid_post_data(
                vehicle=self.other_vehicle.pk,
            ),
        )
        self.assertEqual(RepairOrder.objects.count(), count_before)

    def test_customer_vehicle_mismatch_displays_form_error(self):
        response = self.client.post(
            CREATE_URL,
            self._valid_post_data(
                vehicle=self.other_vehicle.pk,
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")

    def test_invalid_create_post_preserves_customer_and_scoped_valid_vehicle_choice(self):
        response = self.client.post(
            CREATE_URL,
            self._valid_post_data(promised_date="not-a-date"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid date.")
        self.assertContains(response, f'value="{self.customer.pk}" selected')
        self.assertContains(response, f'value="{self.vehicle.pk}" selected')
        self.assertContains(response, VALID_VIN)
        self.assertNotContains(response, VALID_VIN_3)


class RepairOrderIntakeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = make_user(role_name=ROLE_FRONT_DESK)
        cls.customer = make_customer()
        cls.vehicle = make_vehicle(cls.customer)
        cls.other_customer = make_customer(first_name="Other", last_name="Person")
        cls.other_vehicle = make_vehicle(cls.other_customer, vin=VALID_VIN_3)
        cls.customer_detail = reverse("customers:detail", args=[cls.customer.pk])
        cls.vehicle_detail = reverse("vehicles:detail", args=[cls.vehicle.pk])
        cls.customer_intake = reverse("repair_orders:create_for_customer", args=[cls.customer.pk])
        cls.vehicle_intake = reverse("repair_orders:create_for_vehicle", args=[cls.vehicle.pk])

    def setUp(self):
        self.client.force_login(self.staff)

    def assert_cancel_destination(self, response, url):
        self.assertContains(
            response, f'<a class="btn btn-outline-secondary" href="{url}">Cancel</a>', html=True
        )

    def test_new_repair_order_links_from_both_details(self):
        for detail, intake in (
            (self.customer_detail, self.customer_intake),
            (self.vehicle_detail, self.vehicle_intake),
        ):
            with self.subTest(detail=detail):
                self.assertContains(
                    self.client.get(detail),
                    f'<a class="btn btn-primary" href="{intake}">New Repair Order</a>',
                    html=True,
                )

    def test_add_vehicle_returns_to_customer_with_primary_intake_action(self):
        customer = make_customer(first_name="New")
        intake = reverse("repair_orders:create_for_customer", args=[customer.pk])
        add_vehicle = reverse("customers:vehicle_create", args=[customer.pk])
        empty = self.client.get(intake)
        self.assertContains(empty, f'href="{add_vehicle}"')
        self.assertContains(empty, "This customer has no active vehicles.")
        response = self.client.post(
            add_vehicle,
            {"vin": VALID_VIN_2, "make": "Honda", "model": "Fit", "is_active": "on"},
            follow=True,
        )
        self.assertRedirects(response, reverse("customers:detail", args=[customer.pk]))
        self.assertContains(
            response, f'<a class="btn btn-primary" href="{intake}">New Repair Order</a>', html=True
        )
        form = self.client.get(intake).context["form"]
        self.assertEqual(
            form.initial, {"customer": customer.pk, "vehicle": customer.vehicles.get().pk}
        )
        response = self.client.post(intake, form.initial)
        order = RepairOrder.objects.get()
        self.assertEqual((order.customer, order.vehicle), (customer, customer.vehicles.get()))
        self.assertRedirects(response, detail_url(order.pk))

    def test_customer_prefills_sole_active_vehicle(self):
        inactive = make_vehicle(self.customer, vin=VALID_VIN_2, is_active=False)
        response = self.client.get(self.customer_intake)
        self.assertContains(response, f'value="{self.customer.pk}" selected')
        self.assertContains(response, f'value="{self.vehicle.pk}" selected')
        self.assertNotContains(response, inactive.vin)
        self.assertNotContains(response, self.other_vehicle.vin)
        self.assert_cancel_destination(response, self.customer_detail)

    def test_customer_with_multiple_active_vehicles_can_choose(self):
        second = make_vehicle(self.customer, vin=VALID_VIN_2, license_plate="MATCH-02")
        response = self.client.get(self.customer_intake)
        form = response.context["form"]
        self.assertEqual(form["customer"].value(), self.customer.pk)
        self.assertIsNone(form["vehicle"].value())
        self.assertCountEqual(form.fields["vehicle"].queryset, [self.vehicle, second])
        choices = dict(form.fields["vehicle"].choices)
        for vehicle in (self.vehicle, second):
            self.assertTrue(choices[vehicle.pk].startswith(vehicle.vin))
        self.assertContains(response, "Compare vehicle details")
        self.assertContains(response, f"VIN {second.vin} · Plate MATCH-02")
        self.assertNotContains(response, self.other_vehicle.vin)

        response = self.client.post(
            self.customer_intake, {"customer": self.customer.pk, "vehicle": second.pk}
        )
        order = RepairOrder.objects.get()
        self.assertEqual((order.customer, order.vehicle), (self.customer, second))
        self.assertRedirects(response, detail_url(order.pk))

    def test_no_eligible_vehicles_guides_staff_to_add_vehicle(self):
        self.vehicle.is_active = False
        self.vehicle.save(update_fields=["is_active"])
        response = self.client.get(self.customer_intake)
        self.assertContains(response, "This customer has no active vehicles.")
        self.assertContains(
            response, f'href="{reverse("customers:vehicle_create", args=[self.customer.pk])}"'
        )
        self.assertContains(response, 'class="btn btn-primary" disabled>Create Repair Order')
        self.assert_cancel_destination(response, self.customer_detail)
        self.assertNotContains(self.client.get(self.vehicle_detail), "New Repair Order")
        self.assertEqual(self.client.get(self.vehicle_intake).status_code, 404)

    def test_no_vehicles_does_not_show_add_vehicle_without_permission(self):
        customer = make_customer(first_name="No Vehicle")
        user = make_user(username="intake-only", role_name="Intake only")
        self.client.force_login(user)
        with patch.dict(
            ROLE_PERMISSION_MATRIX,
            {"Intake only": {PERM_CUSTOMERS_VIEW, PERM_REPAIR_ORDERS_MANAGE}},
        ):
            response = self.client.get(
                reverse("repair_orders:create_for_customer", args=[customer.pk])
            )
        self.assertContains(response, "This customer has no active vehicles.")
        self.assertNotContains(response, "Add Vehicle")

    def test_vehicle_intake_prefills_owner_and_specific_vehicle(self):
        make_vehicle(self.customer, vin=VALID_VIN_2)
        response = self.client.get(self.vehicle_intake)
        self.assertContains(response, f'value="{self.customer.pk}" selected')
        self.assertContains(response, f'value="{self.vehicle.pk}" selected')
        self.assertNotContains(response, VALID_VIN_2)
        self.assert_cancel_destination(response, self.vehicle_detail)
        response = self.client.post(
            self.vehicle_intake, {"customer": self.customer.pk, "vehicle": self.vehicle.pk}
        )
        order = RepairOrder.objects.get()
        self.assertEqual((order.customer, order.vehicle), (self.customer, self.vehicle))
        self.assertRedirects(response, detail_url(order.pk))

    def test_invalid_input_retains_selections_and_cancel_destination(self):
        for intake, cancel in (
            (self.customer_intake, self.customer_detail),
            (self.vehicle_intake, self.vehicle_detail),
        ):
            with self.subTest(intake=intake):
                response = self.client.post(
                    intake,
                    {
                        "customer": self.customer.pk,
                        "vehicle": self.vehicle.pk,
                        "promised_date": "bad",
                    },
                )
                self.assertContains(response, "Enter a valid date.")
                self.assertContains(response, 'id="id_promised_date_error"')
                self.assertContains(response, 'aria-describedby="id_promised_date_error"')
                self.assertContains(response, f'value="{self.customer.pk}" selected')
                self.assertContains(response, f'value="{self.vehicle.pk}" selected')
                self.assert_cancel_destination(response, cancel)
        self.assertFalse(RepairOrder.objects.exists())

    def test_invalid_or_mismatched_post_does_not_save(self):
        other_same_customer = make_vehicle(self.customer, vin=VALID_VIN_2)
        for intake, customer, vehicle, error_field in (
            (self.customer_intake, self.customer.pk, self.other_vehicle.pk, "vehicle"),
            (self.customer_intake, self.other_customer.pk, self.other_vehicle.pk, "customer"),
            (self.vehicle_intake, self.customer.pk, other_same_customer.pk, "vehicle"),
            (self.vehicle_intake, self.customer.pk, "bad-id", "vehicle"),
        ):
            with self.subTest(intake=intake, customer=customer, vehicle=vehicle):
                response = self.client.post(intake, {"customer": customer, "vehicle": vehicle})
                self.assertContains(response, "Select a valid choice")
                self.assertIn(error_field, response.context["form"].errors)
        self.assertFalse(RepairOrder.objects.exists())

    def test_missing_origin_does_not_prefill(self):
        for name in ("create_for_customer", "create_for_vehicle"):
            url = reverse(f"repair_orders:{name}", args=[999999])
            with self.subTest(name=name):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_users_without_create_permission_do_not_see_or_use_intake(self):
        self.client.force_login(make_user(username="intake-reader", role_name=ROLE_READ_ONLY))
        for detail, intake in (
            (self.customer_detail, self.customer_intake),
            (self.vehicle_detail, self.vehicle_intake),
        ):
            with self.subTest(detail=detail):
                self.assertNotContains(self.client.get(detail), "New Repair Order")
                self.assertEqual(self.client.get(intake).status_code, 403)
                self.assertEqual(self.client.post(intake).status_code, 403)

    def test_standard_create_stays_unscoped_and_cancels_to_list(self):
        response = self.client.get(
            CREATE_URL, {"customer": self.customer.pk, "vehicle": self.vehicle.pk}
        )
        self.assertIsNone(response.context["form"]["customer"].value())
        self.assertIsNone(response.context["form"]["vehicle"].value())
        self.assert_cancel_destination(response, LIST_URL)


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
            self.customer,
            self.vehicle,
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
        self.assertContains(response, VALID_VIN)

    def test_edit_get_scopes_vehicle_choices_to_existing_customer(self):
        response = self.client.get(edit_url(self.ro.pk))

        self.assertContains(response, f'value="{self.vehicle.pk}" selected')
        self.assertContains(response, VALID_VIN)
        self.assertNotContains(response, VALID_VIN_3)

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
        count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        count_after = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self.assertEqual(count_before, count_after)

    def test_customer_vehicle_mismatch_does_not_update_repair_order(self):
        self.client.post(
            edit_url(self.ro.pk),
            self._valid_post_data(
                vehicle=self.other_vehicle.pk,
            ),
        )
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.reported_problem, "Original problem")

    def test_customer_vehicle_mismatch_displays_form_error(self):
        response = self.client.post(
            edit_url(self.ro.pk),
            self._valid_post_data(
                vehicle=self.other_vehicle.pk,
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")

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
        self.ro._apply_status_change(status, changed_by=self.user, note="Final status for test")
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
        count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self.client.post(edit_url(self.ro.pk), self._valid_post_data())
        count_after = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
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
        self.ro = make_repair_order(
            self.customer,
            self.vehicle,
            number="RO-CLOSURE-01",
            status=RepairOrder.Status.READY_FOR_PICKUP,
        )
        # Draft invoice, total = 440, nothing paid → balance_due = 440
        self.invoice = make_invoice(self.ro, number="INV-CLOSURE-01")

    def _post_status(self, new_status, note=""):
        if new_status == "closed":
            RepairOrder.objects.filter(pk=self.ro.pk).update(status="delivered")
            self.ro.refresh_from_db()
        extra = (
            {"transition_action": "cancel", "reason": "Customer canceled"}
            if new_status == "canceled"
            else {}
        )
        return self.client.post(
            status_url(self.ro.pk),
            {"new_status": new_status, "note": note, "expected_status": self.ro.status, **extra},
        )

    # --- blocking behavior ---

    def test_cannot_transition_to_delivered_with_balance_due(self):
        self._post_status("delivered")
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
        count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self._post_status("delivered")
        count_after = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self.assertEqual(count_before, count_after)

    def test_blocked_transition_redirects_to_detail(self):
        response = self._post_status("delivered")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.url).path, detail_url(self.ro.pk))
        self.assertEqual(urlsplit(response.url).fragment, "status-update-card")

    def test_partially_paid_invoice_with_balance_blocks_final_status(self):
        # Pay half the invoice — balance_due is still > 0
        make_payment(self.invoice, Decimal("100.00"))
        self._post_status("delivered")
        self.ro.refresh_from_db()
        self.assertNotEqual(self.ro.status, RepairOrder.Status.DELIVERED)

    # --- allowed behavior ---

    def test_can_transition_to_delivered_with_no_invoice(self):
        ro = make_repair_order(
            self.customer,
            self.vehicle,
            number="RO-NO-INV",
            status=RepairOrder.Status.READY_FOR_PICKUP,
        )
        self.client.post(
            status_url(ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=ro.pk).status,
                "new_status": "delivered",
            },
        )
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
        count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self._post_status("in_repair")
        count_after = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self.assertEqual(count_after, count_before + 1)

    def test_delivered_to_closed_still_succeeds_when_invoice_rule_allows_it(self):
        ro = make_repair_order(self.customer, self.vehicle, number="RO-DELIV-CLOSE")
        ro._apply_status_change(RepairOrder.Status.DELIVERED, changed_by=self.user)
        response = self.client.post(
            status_url(ro.pk),
            {"expected_status": RepairOrder.objects.get(pk=ro.pk).status, "new_status": "closed"},
        )
        self.assertRedirects(response, detail_url(ro.pk))
        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.CLOSED)

    def test_final_repair_order_status_history_remains_visible(self):
        ro = make_repair_order(self.customer, self.vehicle, number="RO-FINAL-HISTORY")
        ro._apply_status_change(RepairOrder.Status.DELIVERED, changed_by=self.user)
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
        self.ro = make_repair_order(
            self.customer,
            self.vehicle,
            number="RO-CLOSURE-HX",
            status=RepairOrder.Status.READY_FOR_PICKUP,
        )
        # Draft invoice with balance due
        self.invoice = make_invoice(self.ro, number="INV-CLOSURE-HX")

    def _htmx_post(self, new_status):
        return self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": new_status,
            },
            HTTP_HX_REQUEST="true",
        )

    def test_htmx_blocked_transition_returns_200(self):
        response = self._htmx_post("delivered")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("HX-Redirect", response.headers)
        self.assertContains(
            response, 'id="status-balance-warning" class="alert alert-warning" tabindex="-1"'
        )

    def test_htmx_blocked_transition_includes_error_message(self):
        response = self._htmx_post("delivered")
        self.assertContains(response, "balance due")

    def test_htmx_blocked_transition_leaves_status_unchanged(self):
        original_status = self.ro.status
        self._htmx_post("delivered")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, original_status)

    def test_htmx_blocked_transition_does_not_create_history(self):
        count_before = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self._htmx_post("delivered")
        count_after = RepairOrderStatusHistory.objects.filter(repair_order=self.ro).count()
        self.assertEqual(count_before, count_after)

    def test_htmx_allowed_transition_still_updates_status(self):
        self._htmx_post("in_repair")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.IN_REPAIR)

    def test_htmx_paid_invoice_allows_final_status(self):
        make_payment(self.invoice, Decimal("440.00"))
        response = self._htmx_post("delivered")
        self.assertEqual(response.headers.get("HX-Redirect"), detail_url(self.ro.pk))
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.DELIVERED)


class RepairOrderPaymentShortcutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = make_user(username="shortcut-manager")
        cls.estimator = make_user(username="shortcut-estimator", role_name=ROLE_ESTIMATOR)
        cls.status_only_role = "Status without billing"
        cls.status_only = make_user(username="shortcut-status-only", role_name=cls.status_only_role)
        customer = make_customer()
        cls.ro = make_repair_order(
            customer, make_vehicle(customer), status=RepairOrder.Status.READY_FOR_PICKUP
        )
        cls.invoice = make_invoice(cls.ro)
        cls.payment_url = reverse("billing:payment_create", kwargs={"invoice_pk": cls.invoice.pk})
        cls.invoice_url = reverse("billing:invoice_detail", kwargs={"pk": cls.invoice.pk})

    def setUp(self):
        self.client.force_login(self.manager)

    def _attempt_status(self, target=RepairOrder.Status.DELIVERED, *, htmx=True):
        headers = {"HX-Request": "true"} if htmx else {}
        return self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": target,
            },
            headers=headers,
            follow=not htmx,
        )

    def _payment_data(self, token, amount):
        return {
            "status_continuation": token,
            "payment_date": "2026-01-15",
            "amount": amount,
            "method": Payment.Method.CASH,
        }

    def _open_shortcut(self, warning):
        url = warning.context["status_payment_url"]
        self.assertContains(warning, f'href="{url}"')
        payment_form = self.client.get(url)
        token = parse_qs(urlsplit(url).query)["status_continuation"][0]
        self.assertContains(payment_form, f'name="status_continuation" value="{token}"')
        return token

    def test_warning_respects_permissions_in_both_post_paths(self):
        role_permissions = {
            self.status_only_role: {PERM_REPAIR_ORDERS_VIEW, PERM_REPAIR_ORDERS_CHANGE_STATUS}
        }
        with patch.dict(ROLE_PERMISSION_MATRIX, role_permissions):
            for htmx in (True, False):
                for user, may_view, may_pay in (
                    (self.manager, True, True),
                    (self.estimator, True, False),
                    (self.status_only, False, False),
                ):
                    with self.subTest(htmx=htmx, user=user.username):
                        self.client.force_login(user)
                        response = self._attempt_status(htmx=htmx)
                        self.assertContains(response, 'id="status-balance-warning"')
                        self.assertEqual(bool(response.context["status_payment_url"]), may_pay)
                        if may_view:
                            self.assertContains(
                                response,
                                f'<a href="{self.invoice_url}">{self.invoice.invoice_number}</a>',
                                html=True,
                            )
                            self.assertContains(response, "has a balance due of $440.00.")
                        else:
                            self.assertContains(
                                response,
                                "Repair order cannot be marked delivered because "
                                f"invoice {self.invoice.invoice_number} has a balance due.",
                            )
                            self.assertNotContains(response, self.invoice_url)
                            self.assertNotContains(response, "$440.00")
                        if may_pay:
                            self.assertContains(response, 'aria-describedby="status-payment-hint"')
                            self.assertContains(response, "Record payment")
                            self.assertContains(
                                response,
                                "Just received payment? Enter the amount here, "
                                "then retry the status update.",
                            )
                        else:
                            self.assertNotContains(response, self.payment_url)
                            self.assertNotContains(response, "Just received payment?")

    def test_invoice_on_final_repair_order_cannot_offer_payment(self):
        RepairOrder.objects.filter(pk=self.ro.pk).update(status=RepairOrder.Status.DELIVERED)
        response = self._attempt_status(RepairOrder.Status.CLOSED)
        self.assertContains(response, "has a balance due of $440.00.")
        self.assertNotContains(response, self.payment_url)

    def test_full_payment_preselects_closed_but_waits_for_confirmation(self):
        token = self._open_shortcut(self._attempt_status())
        response = self.client.post(
            self.payment_url, self._payment_data(token, "440.00"), follow=True
        )
        self.assertEqual(urlsplit(response.redirect_chain[-1][0]).fragment, "status-update-card")
        self.assertContains(
            response,
            "Invoice paid in full. Select Update Status to mark this repair order as delivered.",
        )
        self.assertContains(
            response, '<option value="delivered" selected>Delivered</option>', html=True
        )
        self.invoice.refresh_from_db()
        self.ro.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PAID)
        self.assertEqual(self.invoice.payments.get().method, Payment.Method.CASH)
        self.assertEqual(self.ro.status, RepairOrder.Status.READY_FOR_PICKUP)
        self.assertEqual(self.ro.status_history.count(), 1)

        self._attempt_status()
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.DELIVERED)
        self.assertEqual(self.ro.status_history.first().new_status, RepairOrder.Status.DELIVERED)

    def test_reopening_payment_return_url_after_closure_clears_confirmation(self):
        confirmation = (
            "Invoice paid in full. Select Update Status to mark this repair order as delivered."
        )
        token = self._open_shortcut(self._attempt_status())
        payment = self.client.post(self.payment_url, self._payment_data(token, "440.00"))
        self.assertEqual(payment.status_code, 302)
        return_url = payment["Location"]
        pending = self.client.get(return_url)
        self.assertContains(pending, confirmation)
        self.assertContains(
            pending, '<option value="delivered" selected>Delivered</option>', html=True
        )

        self._attempt_status(htmx=False)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.DELIVERED)
        self.assertEqual(self.invoice.payments.count(), 1)

        completed = self.client.get(return_url)
        self.assertContains(
            completed, '<option value="" selected>Choose next status…</option>', html=True
        )
        self.assertContains(completed, '<option value="closed">Closed</option>', html=True)
        self.assertNotContains(completed, confirmation)
        self.assertNotContains(completed, 'id="status-balance-warning"')
        self.assertNotContains(completed, 'id="status-payment-hint"')
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.DELIVERED)
        self.assertEqual(self.invoice.payments.count(), 1)

    def test_htmx_closure_after_payment_redirects_to_clean_updated_detail(self):
        token = self._open_shortcut(self._attempt_status())
        payment = self.client.post(self.payment_url, self._payment_data(token, "440.00"))
        self.assertEqual(payment.status_code, 302)
        return_url = payment["Location"]
        self.assertIn("status_continuation", parse_qs(urlsplit(return_url).query))
        self.assertContains(self.client.get(return_url), "Edit Repair Order")

        response = self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": RepairOrder.Status.DELIVERED,
                "note": "Customer collected vehicle.",
            },
            headers={"HX-Request": "true", "HX-Current-URL": f"http://testserver{return_url}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("HX-Redirect"), detail_url(self.ro.pk))

        detail = self.client.get(response["HX-Redirect"])
        self.assertContains(
            detail,
            '<span id="ro-status-badge" class="status-badge status-delivered" '
            'hx-swap-oob="true">Delivered</span>',
            html=True,
        )
        self.assertContains(detail, "Status updated to &quot;Delivered&quot;.")
        self.assertContains(detail, "<td>Delivered</td>", html=True)
        self.assertContains(detail, "<td>Customer collected vehicle.</td>", html=True)
        self.assertNotContains(detail, "Edit Repair Order")
        self.assertNotContains(detail, "status_continuation")

    def test_partial_payment_and_validation_keep_delivered_for_second_payment(self):
        target = RepairOrder.Status.DELIVERED
        token = self._open_shortcut(self._attempt_status(target, htmx=False))

        invalid = self.client.post(self.payment_url, self._payment_data(token, "0.00"))
        self.assertContains(invalid, f'name="status_continuation" value="{token}"')
        self.assertContains(invalid, "Amount must be greater than zero.")
        self.assertFalse(self.invoice.payments.exists())

        partial = self.client.post(
            self.payment_url, self._payment_data(token, "140.00"), follow=True
        )
        self.assertContains(partial, "has a remaining balance of $300.00.")
        self.assertContains(partial, "Record another payment")
        self.assertContains(
            partial, '<option value="delivered" selected>Delivered</option>', html=True
        )
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.PARTIALLY_PAID)
        self.assertContains(self._attempt_status(target), "has a balance due of $300.00.")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.READY_FOR_PICKUP)

        second_token = self._open_shortcut(partial)
        paid = self.client.post(
            self.payment_url, self._payment_data(second_token, "300.00"), follow=True
        )
        self.assertContains(
            paid,
            "Invoice paid in full. Select Update Status to mark this repair order as delivered.",
        )
        self.assertContains(
            paid, '<option value="delivered" selected>Delivered</option>', html=True
        )
        self.assertNotContains(paid, "Record another payment")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.READY_FOR_PICKUP)
        self._attempt_status(target)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, target)

        completed = self.client.get(paid.redirect_chain[-1][0])
        self.assertNotContains(
            completed,
            "Invoice paid in full. Select Update Status to mark this repair order as delivered.",
        )
        self.assertNotContains(completed, 'id="status-balance-warning"')
        self.assertNotContains(completed, 'id="status-payment-hint"')

    def test_invalid_or_other_invoice_continuation_uses_normal_return(self):
        token = self._open_shortcut(self._attempt_status())
        other_order = make_repair_order(self.ro.customer, self.ro.vehicle, number="RO-OTHER")
        other_invoice = make_invoice(other_order, number="INV-OTHER")
        for invalid_token in (
            token + "tampered",
            sign_status_continuation(other_invoice, RepairOrder.Status.DELIVERED),
            sign_status_continuation(self.invoice, "unknown_status"),
        ):
            with self.subTest(token=invalid_token):
                response = self.client.post(
                    self.payment_url, self._payment_data(invalid_token, "1.00")
                )
                self.assertRedirects(response, detail_url(self.ro.pk))
        self.assertFalse(self.invoice.payments.exists())
        self.assertFalse(other_invoice.payments.exists())
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.READY_FOR_PICKUP)

    def test_stale_continuation_after_status_access_is_removed(self):
        token = self._open_shortcut(self._attempt_status())
        self.manager.groups.set([Group.objects.get_or_create(name=ROLE_FRONT_DESK)[0]])
        paid = self.client.post(self.payment_url, self._payment_data(token, "440.00"), follow=True)
        target_url, _ = paid.redirect_chain[-1]
        self.assertEqual(target_url, detail_url(self.ro.pk))
        self.assertNotContains(paid, 'id="status-update-card"')
        response = self.client.post(
            status_url(self.ro.pk),
            {
                "expected_status": RepairOrder.objects.get(pk=self.ro.pk).status,
                "new_status": RepairOrder.Status.DELIVERED,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.READY_FOR_PICKUP)

    def test_already_reached_status_does_not_show_stale_warning(self):
        url = self._attempt_status(htmx=False).redirect_chain[-1][0]
        make_payment(self.invoice, Decimal("440.00"))
        self.ro._apply_status_change(RepairOrder.Status.CLOSED, changed_by=self.manager)

        response = self.client.get(url)
        self.assertContains(response, "Current status: <strong>Closed</strong>", html=True)
        self.assertNotContains(response, 'id="status-balance-warning"')
        self.assertNotContains(response, self.payment_url)


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
        if role_name == ROLE_TECHNICIAN:
            self.ro.assigned_to = user
            self.ro.save(update_fields=["assigned_to", "updated_at"])
        return user

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
