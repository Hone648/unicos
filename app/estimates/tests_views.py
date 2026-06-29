from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.authorization import (
    ROLE_MANAGER,
    ROLE_READ_ONLY,
)
from customers.models import Customer
from estimates.models import Estimate
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def assign_role(user, role_name):
    group, _created = Group.objects.get_or_create(name=role_name)
    user.groups.add(group)
    return user


def make_user(username="staffer", role_name=ROLE_MANAGER):
    user = get_user_model().objects.create_user(
        username=username, password="pw-test-12345"
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
    defaults = {"make": "Honda", "model": "Civic", "year": 2021}
    defaults.update(kwargs)
    return Vehicle.objects.create(customer=customer, vin=vin, **defaults)


def make_repair_order(customer, vehicle, number="RO-EST-V-001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number=number, **kwargs
    )


def make_estimate(repair_order, number="EST-V-001", **kwargs):
    return Estimate.objects.create(
        repair_order=repair_order, estimate_number=number, **kwargs
    )


def create_url(ro_pk):
    return reverse("estimates:create", kwargs={"repair_order_pk": ro_pk})


def detail_url(pk):
    return reverse("estimates:detail", kwargs={"pk": pk})


def print_url(pk):
    return reverse("estimates:print", kwargs={"pk": pk})


def edit_url(pk):
    return reverse("estimates:edit", kwargs={"pk": pk})


def ro_detail_url(pk):
    return reverse("repair_orders:detail", kwargs={"pk": pk})


def li_create_url(estimate_pk):
    return reverse("estimates:line_item_create", kwargs={"estimate_pk": estimate_pk})


def li_edit_url(pk):
    return reverse("estimates:line_item_edit", kwargs={"pk": pk})


def li_delete_url(pk):
    return reverse("estimates:line_item_delete", kwargs={"pk": pk})


def supplement_create_url(pk):
    return reverse("estimates:supplement_create", kwargs={"pk": pk})


def make_line_item(estimate, **kwargs):
    from estimates.models import EstimateLineItem
    defaults = {
        "item_type": EstimateLineItem.ItemType.LABOR,
        "description": "Labor",
        "quantity": Decimal("1.00"),
        "unit_price": Decimal("100.00"),
    }
    defaults.update(kwargs)
    return EstimateLineItem.objects.create(estimate=estimate, **defaults)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class EstimateAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.estimate = make_estimate(self.ro)

    def test_create_requires_login(self):
        url = create_url(self.ro.pk)
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")

    def test_detail_requires_login(self):
        url = detail_url(self.estimate.pk)
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")

    def test_print_requires_login(self):
        url = print_url(self.estimate.pk)
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")

    def test_edit_requires_login(self):
        url = edit_url(self.estimate.pk)
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class EstimatePermissionTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.estimate = make_estimate(self.ro)

    def test_view_permission_can_view_detail(self):
        self.client.force_login(make_user("ro-viewer", ROLE_READ_ONLY))
        self.assertEqual(self.client.get(detail_url(self.estimate.pk)).status_code, 200)

    def test_view_permission_can_view_print_page(self):
        self.client.force_login(make_user("ro-viewer", ROLE_READ_ONLY))
        self.assertEqual(self.client.get(print_url(self.estimate.pk)).status_code, 200)

    def test_no_role_user_forbidden_for_detail(self):
        self.client.force_login(make_user("no-role", role_name=None))
        self.assertEqual(self.client.get(detail_url(self.estimate.pk)).status_code, 403)

    def test_no_role_user_forbidden_for_print_page(self):
        self.client.force_login(make_user("no-role", role_name=None))
        self.assertEqual(self.client.get(print_url(self.estimate.pk)).status_code, 403)

    def test_view_only_user_forbidden_for_create(self):
        self.client.force_login(make_user("ro-viewer", ROLE_READ_ONLY))
        self.assertEqual(self.client.get(create_url(self.ro.pk)).status_code, 403)

    def test_view_only_user_forbidden_for_edit(self):
        self.client.force_login(make_user("ro-viewer", ROLE_READ_ONLY))
        self.assertEqual(self.client.get(edit_url(self.estimate.pk)).status_code, 403)

    def test_manage_user_can_open_create(self):
        self.client.force_login(make_user("manager", ROLE_MANAGER))
        self.assertEqual(self.client.get(create_url(self.ro.pk)).status_code, 200)

    def test_manage_user_can_open_edit(self):
        self.client.force_login(make_user("manager", ROLE_MANAGER))
        self.assertEqual(self.client.get(edit_url(self.estimate.pk)).status_code, 200)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class EstimateCreateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def _valid_data(self, **overrides):
        data = {
            "status": Estimate.Status.DRAFT,
            "insurance_company": "Acme Insurance",
            "claim_number": "CLM-9",
            "deductible": "500.00",
            "estimated_total": "2500.00",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        self.assertEqual(self.client.get(create_url(self.ro.pk)).status_code, 200)

    def test_form_does_not_expose_estimate_number(self):
        response = self.client.get(create_url(self.ro.pk))
        self.assertNotContains(response, 'name="estimate_number"')
        self.assertNotContains(response, 'name="repair_order"')

    def test_valid_post_creates_estimate(self):
        self.client.post(create_url(self.ro.pk), self._valid_data())
        self.assertEqual(Estimate.objects.filter(repair_order=self.ro).count(), 1)

    def test_valid_post_assigns_repair_order_from_url(self):
        self.client.post(create_url(self.ro.pk), self._valid_data())
        estimate = Estimate.objects.get(repair_order=self.ro)
        self.assertEqual(estimate.repair_order, self.ro)

    def test_valid_post_generates_estimate_number(self):
        self.client.post(create_url(self.ro.pk), self._valid_data())
        estimate = Estimate.objects.get(repair_order=self.ro)
        self.assertRegex(estimate.estimate_number, r"^EST-\d{4}-\d{6}$")

    def test_valid_post_sets_created_and_updated_by(self):
        self.client.post(create_url(self.ro.pk), self._valid_data())
        estimate = Estimate.objects.get(repair_order=self.ro)
        self.assertEqual(estimate.created_by, self.user)
        self.assertEqual(estimate.updated_by, self.user)

    def test_valid_post_redirects_to_detail(self):
        response = self.client.post(create_url(self.ro.pk), self._valid_data())
        estimate = Estimate.objects.get(repair_order=self.ro)
        self.assertRedirects(response, detail_url(estimate.pk))

    def test_blank_insurance_fields_create_estimate(self):
        self.client.post(
            create_url(self.ro.pk),
            self._valid_data(insurance_company="", claim_number=""),
        )
        self.assertEqual(Estimate.objects.filter(repair_order=self.ro).count(), 1)

    def test_invalid_post_does_not_create_estimate(self):
        response = self.client.post(
            create_url(self.ro.pk), self._valid_data(deductible="-1.00")
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Estimate.objects.filter(repair_order=self.ro).exists())

    def test_invalid_post_shows_field_error(self):
        response = self.client.post(
            create_url(self.ro.pk), self._valid_data(estimated_total="-1.00")
        )
        self.assertContains(response, "Estimated total cannot be negative.")

    def test_multiple_estimates_can_be_created_for_one_ro(self):
        self.client.post(create_url(self.ro.pk), self._valid_data())
        self.client.post(create_url(self.ro.pk), self._valid_data())
        self.assertEqual(Estimate.objects.filter(repair_order=self.ro).count(), 2)


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

class EstimateDetailTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user())
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.estimate = make_estimate(
            self.ro,
            number="EST-DETAIL-1",
            insurance_company="Geico",
            claim_number="CLM-DETAIL",
            deductible=Decimal("250.00"),
            estimated_total=Decimal("1800.00"),
        )

    def test_get_returns_200(self):
        self.assertEqual(self.client.get(detail_url(self.estimate.pk)).status_code, 200)

    def test_detail_shows_estimate_fields(self):
        response = self.client.get(detail_url(self.estimate.pk))
        self.assertContains(response, "EST-DETAIL-1")
        self.assertContains(response, "Geico")
        self.assertContains(response, "CLM-DETAIL")
        self.assertContains(response, "250.00")
        self.assertContains(response, "1800.00")

    def test_detail_links_to_repair_order(self):
        response = self.client.get(detail_url(self.estimate.pk))
        self.assertContains(response, ro_detail_url(self.ro.pk))

    def test_detail_shows_edit_link_with_manage_permission(self):
        response = self.client.get(detail_url(self.estimate.pk))
        self.assertContains(response, edit_url(self.estimate.pk))

    def test_detail_shows_print_link(self):
        response = self.client.get(detail_url(self.estimate.pk))
        self.assertContains(response, print_url(self.estimate.pk))

    def test_detail_hides_edit_link_without_manage_permission(self):
        self.client.logout()
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        response = self.client.get(detail_url(self.estimate.pk))
        self.assertNotContains(response, edit_url(self.estimate.pk))


# ---------------------------------------------------------------------------
# Print
# ---------------------------------------------------------------------------

class EstimatePrintTests(TestCase):
    def setUp(self):
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        self.customer = make_customer(
            first_name="Avery",
            last_name="Reed",
            phone_primary="555-0101",
            email="avery@example.test",
        )
        self.vehicle = make_vehicle(
            self.customer,
            make="Toyota",
            model="Camry",
            year=2020,
        )
        self.ro = make_repair_order(
            self.customer,
            self.vehicle,
            number="RO-PRINT-001",
        )
        self.estimate = make_estimate(
            self.ro,
            number="EST-PRINT-001",
            insurance_company="Acme Insurance",
            claim_number="CLM-PRINT",
            deductible=Decimal("500.00"),
            estimated_total=Decimal("0.00"),
            notes="Customer approved printed estimate.",
        )

    def test_print_page_shows_estimate_context_and_line_items(self):
        make_line_item(
            self.estimate,
            description="Refinish quarter panel",
            quantity=Decimal("2.00"),
            unit_price=Decimal("125.00"),
        )
        self.estimate.refresh_from_db()

        response = self.client.get(print_url(self.estimate.pk))

        self.assertContains(response, "Estimate")
        self.assertContains(response, "EST-PRINT-001")
        self.assertContains(response, "RO-PRINT-001")
        self.assertContains(response, "Avery Reed")
        self.assertContains(response, "Toyota Camry")
        self.assertContains(response, VALID_VIN)
        self.assertContains(response, "Acme Insurance")
        self.assertContains(response, "CLM-PRINT")
        self.assertContains(response, "500.00")
        self.assertContains(response, "Refinish quarter panel")
        self.assertContains(response, "250.00")
        self.assertContains(response, "Customer approved printed estimate.")

    def test_print_page_uses_manual_total_when_no_line_items(self):
        self.estimate.estimated_total = Decimal("875.00")
        self.estimate.save()

        response = self.client.get(print_url(self.estimate.pk))

        self.assertContains(response, "No estimate line items are present.")
        self.assertContains(response, "Showing manual estimated total.")
        self.assertContains(response, "875.00")

    def test_print_page_shows_supplement_parent_context(self):
        supplement = make_estimate(
            self.ro,
            number="EST-SUP-001",
            kind=Estimate.Kind.SUPPLEMENT,
            parent_estimate=self.estimate,
            estimated_total=Decimal("300.00"),
        )

        response = self.client.get(print_url(supplement.pk))

        self.assertContains(response, "Supplement")
        self.assertContains(response, "Supplement of")
        self.assertContains(response, "EST-PRINT-001")
        self.assertContains(response, detail_url(self.estimate.pk))


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------

class EstimateEditTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.estimate = make_estimate(
            self.ro,
            number="EST-EDIT-1",
            estimated_total=Decimal("1000.00"),
        )

    def _valid_data(self, **overrides):
        data = {
            "status": Estimate.Status.SUBMITTED,
            "insurance_company": "Progressive",
            "claim_number": "CLM-EDIT",
            "deductible": "100.00",
            "estimated_total": "1500.00",
            "notes": "Updated",
        }
        data.update(overrides)
        return data

    def test_get_returns_200(self):
        self.assertEqual(self.client.get(edit_url(self.estimate.pk)).status_code, 200)

    def test_get_shows_existing_values(self):
        response = self.client.get(edit_url(self.estimate.pk))
        self.assertContains(response, "EST-EDIT-1")

    def test_valid_post_updates_estimate(self):
        self.client.post(edit_url(self.estimate.pk), self._valid_data())
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("1500.00"))
        self.assertEqual(self.estimate.status, Estimate.Status.SUBMITTED)

    def test_valid_post_sets_updated_by(self):
        updater = make_user("updater")
        self.client.logout()
        self.client.force_login(updater)
        self.client.post(edit_url(self.estimate.pk), self._valid_data())
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.updated_by, updater)

    def test_valid_post_redirects_to_detail(self):
        response = self.client.post(edit_url(self.estimate.pk), self._valid_data())
        self.assertRedirects(response, detail_url(self.estimate.pk))

    def test_invalid_post_does_not_mutate(self):
        self.client.post(edit_url(self.estimate.pk), self._valid_data(deductible="-5.00"))
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("1000.00"))

    def test_edit_does_not_change_estimate_number(self):
        original_number = self.estimate.estimate_number
        self.client.post(edit_url(self.estimate.pk), self._valid_data())
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimate_number, original_number)


# ---------------------------------------------------------------------------
# Repair-order detail integration
# ---------------------------------------------------------------------------

class RepairOrderDetailEstimateIntegrationTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_detail_shows_estimate_summary_section(self):
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, "Estimates")

    def test_detail_lists_existing_estimate(self):
        estimate = make_estimate(
            self.ro, number="EST-SUMMARY", insurance_company="Allstate"
        )
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, "EST-SUMMARY")
        self.assertContains(response, "Allstate")
        self.assertContains(response, detail_url(estimate.pk))

    def test_detail_shows_create_link_with_manage_permission(self):
        self.client.force_login(make_user("manager", ROLE_MANAGER))
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, create_url(self.ro.pk))

    def test_detail_hides_create_link_without_manage_permission(self):
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertNotContains(response, create_url(self.ro.pk))

    def test_detail_shows_empty_state_when_no_estimates(self):
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        response = self.client.get(ro_detail_url(self.ro.pk))
        self.assertContains(response, "No estimates on file")


# ---------------------------------------------------------------------------
# Line item: authentication & permissions
# ---------------------------------------------------------------------------

class LineItemAuthTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.estimate = make_estimate(self.ro)
        self.item = make_line_item(self.estimate)

    def test_create_requires_login(self):
        url = li_create_url(self.estimate.pk)
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")

    def test_edit_requires_login(self):
        url = li_edit_url(self.item.pk)
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")

    def test_delete_requires_login(self):
        url = li_delete_url(self.item.pk)
        self.assertRedirects(self.client.post(url), f"/accounts/login/?next={url}")

    def test_view_only_user_forbidden_for_create(self):
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        self.assertEqual(self.client.get(li_create_url(self.estimate.pk)).status_code, 403)

    def test_view_only_user_forbidden_for_edit(self):
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        self.assertEqual(self.client.get(li_edit_url(self.item.pk)).status_code, 403)

    def test_view_only_user_forbidden_for_delete(self):
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        self.assertEqual(self.client.post(li_delete_url(self.item.pk)).status_code, 403)


# ---------------------------------------------------------------------------
# Line item: create / edit / delete
# ---------------------------------------------------------------------------

class LineItemCreateEditDeleteTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.estimate = make_estimate(self.ro, number="EST-LI-V", estimated_total=Decimal("0.00"))

    def _data(self, **overrides):
        from estimates.models import EstimateLineItem
        data = {
            "item_type": EstimateLineItem.ItemType.LABOR,
            "description": "Refinish labor",
            "quantity": "2.00",
            "unit_price": "75.00",
        }
        data.update(overrides)
        return data

    def test_create_get_returns_200(self):
        self.assertEqual(self.client.get(li_create_url(self.estimate.pk)).status_code, 200)

    def test_manage_user_can_open_edit(self):
        item = make_line_item(self.estimate)
        self.assertEqual(self.client.get(li_edit_url(item.pk)).status_code, 200)

    def test_valid_create_adds_line_item_and_redirects(self):
        response = self.client.post(li_create_url(self.estimate.pk), self._data())
        self.assertRedirects(response, detail_url(self.estimate.pk))
        self.assertEqual(self.estimate.line_items.count(), 1)

    def test_valid_create_recalculates_total(self):
        self.client.post(li_create_url(self.estimate.pk), self._data())
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("150.00"))

    def test_invalid_create_does_not_add(self):
        response = self.client.post(li_create_url(self.estimate.pk), self._data(quantity="0.00"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quantity must be greater than zero.")
        self.assertEqual(self.estimate.line_items.count(), 0)

    def test_valid_edit_updates_and_recalculates(self):
        item = make_line_item(self.estimate, quantity=Decimal("1.00"), unit_price=Decimal("100.00"))
        self.client.post(li_edit_url(item.pk), self._data(quantity="3.00", unit_price="50.00"))
        item.refresh_from_db()
        self.estimate.refresh_from_db()
        self.assertEqual(item.quantity, Decimal("3.00"))
        self.assertEqual(self.estimate.estimated_total, Decimal("150.00"))

    def test_invalid_edit_does_not_mutate(self):
        item = make_line_item(self.estimate, quantity=Decimal("1.00"), unit_price=Decimal("100.00"))
        self.client.post(li_edit_url(item.pk), self._data(unit_price="-5.00"))
        item.refresh_from_db()
        self.assertEqual(item.unit_price, Decimal("100.00"))

    def test_delete_via_post_removes_and_recalculates(self):
        item = make_line_item(self.estimate, quantity=Decimal("1.00"), unit_price=Decimal("100.00"))
        make_line_item(self.estimate, quantity=Decimal("1.00"), unit_price=Decimal("40.00"))
        response = self.client.post(li_delete_url(item.pk))
        self.assertRedirects(response, detail_url(self.estimate.pk))
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.line_items.count(), 1)
        self.assertEqual(self.estimate.estimated_total, Decimal("40.00"))

    def test_delete_via_get_does_not_remove(self):
        item = make_line_item(self.estimate)
        response = self.client.get(li_delete_url(item.pk))
        self.assertRedirects(response, detail_url(self.estimate.pk))
        self.assertTrue(self.estimate.line_items.filter(pk=item.pk).exists())

    def test_detail_shows_line_items_and_total(self):
        make_line_item(self.estimate, description="Blend panel", quantity=Decimal("2.00"), unit_price=Decimal("60.00"))
        response = self.client.get(detail_url(self.estimate.pk))
        self.assertContains(response, "Blend panel")
        self.assertContains(response, "120.00")

    def test_detail_line_item_actions_hidden_without_manage(self):
        item = make_line_item(self.estimate)
        self.client.logout()
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        response = self.client.get(detail_url(self.estimate.pk))
        self.assertNotContains(response, li_edit_url(item.pk))
        self.assertNotContains(response, li_create_url(self.estimate.pk))


# ---------------------------------------------------------------------------
# Supplement create
# ---------------------------------------------------------------------------

class SupplementCreateTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.parent = make_estimate(
            self.ro, number="EST-PARENT-V",
            insurance_company="Acme", claim_number="CLM-P", deductible=Decimal("500.00"),
        )

    def _data(self, **overrides):
        data = {
            "status": Estimate.Status.DRAFT,
            "insurance_company": "Acme",
            "claim_number": "CLM-P",
            "deductible": "500.00",
            "estimated_total": "0.00",
            "notes": "",
        }
        data.update(overrides)
        return data

    def test_create_requires_login(self):
        url = supplement_create_url(self.parent.pk)
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")

    def test_view_only_user_forbidden(self):
        self.client.force_login(make_user("viewer", ROLE_READ_ONLY))
        self.assertEqual(self.client.get(supplement_create_url(self.parent.pk)).status_code, 403)

    def test_manage_user_can_open_form(self):
        self.client.force_login(self.user)
        response = self.client.get(supplement_create_url(self.parent.pk))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.parent.estimate_number)

    def test_form_seeds_parent_insurance_values(self):
        self.client.force_login(self.user)
        response = self.client.get(supplement_create_url(self.parent.pk))
        self.assertContains(response, "Acme")

    def test_valid_create_sets_supplement_fields(self):
        self.client.force_login(self.user)
        response = self.client.post(supplement_create_url(self.parent.pk), self._data())
        supplement = Estimate.objects.exclude(pk=self.parent.pk).get(repair_order=self.ro)
        self.assertEqual(supplement.kind, Estimate.Kind.SUPPLEMENT)
        self.assertEqual(supplement.parent_estimate, self.parent)
        self.assertEqual(supplement.repair_order, self.ro)
        self.assertRegex(supplement.estimate_number, r"^EST-\d{4}-\d{6}$")
        self.assertEqual(supplement.created_by, self.user)
        self.assertRedirects(response, detail_url(supplement.pk))

    def test_invalid_create_does_not_create(self):
        self.client.force_login(self.user)
        count_before = Estimate.objects.count()
        response = self.client.post(supplement_create_url(self.parent.pk), self._data(deductible="-1.00"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Estimate.objects.count(), count_before)

    def test_detail_shows_supplement_link_on_parent(self):
        self.client.force_login(self.user)
        self.client.post(supplement_create_url(self.parent.pk), self._data())
        supplement = Estimate.objects.exclude(pk=self.parent.pk).get(repair_order=self.ro)
        response = self.client.get(detail_url(self.parent.pk))
        self.assertContains(response, supplement.estimate_number)
        self.assertContains(response, detail_url(supplement.pk))

    def test_supplement_detail_links_back_to_parent(self):
        self.client.force_login(self.user)
        self.client.post(supplement_create_url(self.parent.pk), self._data())
        supplement = Estimate.objects.exclude(pk=self.parent.pk).get(repair_order=self.ro)
        response = self.client.get(detail_url(supplement.pk))
        self.assertContains(response, self.parent.estimate_number)
        self.assertContains(response, detail_url(self.parent.pk))
