from decimal import Decimal

from customers.models import Customer
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from estimates.admin import EstimateAdmin, EstimateLineItemAdmin, EstimateLineItemInline
from estimates.models import Estimate, EstimateLineItem
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
        estimate = Estimate.objects.create(repair_order=self.ro, estimate_number="EST-ADM-DISP")
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


# ---------------------------------------------------------------------------
# Supplement / line-item admin
# ---------------------------------------------------------------------------


class EstimateAdminSupplementFieldsTests(TestCase):
    def test_admin_exposes_kind_and_parent_estimate(self):
        instance = EstimateAdmin(Estimate, admin.site)
        self.assertIn("kind", instance.list_display)
        self.assertIn("parent_estimate", instance.list_display)
        self.assertIn("kind", instance.list_filter)

    def test_admin_includes_line_item_inline(self):
        instance = EstimateAdmin(Estimate, admin.site)
        self.assertIn(EstimateLineItemInline, instance.inlines)


class EstimateAdminApprovalFieldsTests(TestCase):
    def test_admin_exposes_approval_fields(self):
        instance = EstimateAdmin(Estimate, admin.site)
        self.assertIn("approval_source", instance.list_display)
        self.assertIn("approval_contact_name", instance.list_display)
        self.assertIn("approved_at", instance.list_display)
        self.assertIn("approval_source", instance.list_filter)

    def test_admin_includes_approval_fieldset(self):
        instance = EstimateAdmin(Estimate, admin.site)
        fieldset_names = [name for name, _options in instance.fieldsets]
        self.assertIn("Approval", fieldset_names)


class EstimateLineItemAdminTests(TestCase):
    def setUp(self):
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle)
        self.estimate = Estimate.objects.create(
            repair_order=ro,
            estimate_number="EST-LI-ADM",
        )
        self.item = EstimateLineItem.objects.create(
            estimate=self.estimate,
            item_type=EstimateLineItem.ItemType.PARTS,
            description="Bumper cover",
            quantity=Decimal("1.00"),
            unit_price=Decimal("250.00"),
        )

    def test_line_item_admin_is_registered(self):
        self.assertIn(EstimateLineItem, admin.site._registry)
        self.assertIs(admin.site._registry[EstimateLineItem].__class__, EstimateLineItemAdmin)

    def test_line_total_display(self):
        instance = EstimateLineItemAdmin(EstimateLineItem, admin.site)
        self.assertEqual(instance.line_total_display(self.item), Decimal("250.00"))


class EstimateLineItemAdminChangeListTests(TestCase):
    def setUp(self):
        self.client.force_login(make_superuser())
        customer = make_customer()
        vehicle = make_vehicle(customer)
        ro = make_repair_order(customer, vehicle)
        estimate = Estimate.objects.create(
            repair_order=ro,
            estimate_number="EST-LI-CL",
        )
        self.item = EstimateLineItem.objects.create(
            estimate=estimate,
            item_type=EstimateLineItem.ItemType.LABOR,
            description="Frame pull",
            quantity=Decimal("1.00"),
            unit_price=Decimal("400.00"),
        )

    def test_changelist_loads(self):
        url = reverse("admin:estimates_estimatelineitem_changelist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Frame pull")

    def test_changelist_search_works(self):
        url = reverse("admin:estimates_estimatelineitem_changelist")
        response = self.client.get(url, {"q": "Frame pull"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Frame pull")


# ---------------------------------------------------------------------------
# Admin save_model status routing (Slice 43)
# ---------------------------------------------------------------------------


class MockEstimateStatusChangeForm:
    """Minimal form stub for EstimateAdmin.save_model routing tests."""

    def __init__(self, initial_status, new_status=None, cleaned_data=None):
        self.initial = {"status": initial_status}
        self.cleaned_data = cleaned_data or {}
        if new_status is not None and new_status != initial_status:
            self.changed_data = ["status"]
        else:
            self.changed_data = []


class EstimateAdminSaveModelStatusRoutingTests(TestCase):
    """Admin save_model routes status changes through transition_estimate_status."""

    def setUp(self):
        self.admin_instance = EstimateAdmin(Estimate, admin.site)
        self.user = make_user(username="admin-status")
        self.request = make_request(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def _estimate(self, number, status=Estimate.Status.DRAFT, **kwargs):
        return Estimate.objects.create(
            repair_order=self.ro, estimate_number=number, status=status, **kwargs
        )

    def test_save_model_allows_draft_to_submitted(self):
        estimate = self._estimate("EST-ADM-SUB")
        form = MockEstimateStatusChangeForm(
            initial_status=Estimate.Status.DRAFT,
            new_status=Estimate.Status.SUBMITTED,
        )
        estimate.status = Estimate.Status.SUBMITTED
        self.admin_instance.save_model(self.request, estimate, form, change=True)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.SUBMITTED)

    def test_save_model_blocks_approval_without_approval_capture(self):
        estimate = self._estimate("EST-ADM-NOCAP", status=Estimate.Status.SUBMITTED)
        form = MockEstimateStatusChangeForm(
            initial_status=Estimate.Status.SUBMITTED,
            new_status=Estimate.Status.APPROVED,
            cleaned_data={},
        )
        estimate.status = Estimate.Status.APPROVED
        self.admin_instance.save_model(self.request, estimate, form, change=True)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.SUBMITTED)
        self.assertIsNone(estimate.approved_at)

    def test_save_model_approves_with_valid_approval_capture(self):
        estimate = self._estimate("EST-ADM-CAP", status=Estimate.Status.SUBMITTED)
        form = MockEstimateStatusChangeForm(
            initial_status=Estimate.Status.SUBMITTED,
            new_status=Estimate.Status.APPROVED,
            cleaned_data={
                "approval_source": Estimate.ApprovalSource.CUSTOMER,
                "approval_contact_name": "Jane Doe",
            },
        )
        estimate.status = Estimate.Status.APPROVED
        self.admin_instance.save_model(self.request, estimate, form, change=True)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.APPROVED)
        self.assertIsNotNone(estimate.approved_at)
        self.assertEqual(estimate.approval_contact_name, "Jane Doe")

    def test_save_model_blocks_approved_back_to_draft(self):
        estimate = self._estimate(
            "EST-ADM-BACK",
            status=Estimate.Status.APPROVED,
            approval_source=Estimate.ApprovalSource.CUSTOMER,
            approval_contact_name="Jane Doe",
        )
        estimate.approved_at = timezone.now()
        estimate.save(update_fields=["approved_at"])
        form = MockEstimateStatusChangeForm(
            initial_status=Estimate.Status.APPROVED,
            new_status=Estimate.Status.DRAFT,
        )
        estimate.status = Estimate.Status.DRAFT
        self.admin_instance.save_model(self.request, estimate, form, change=True)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.APPROVED)

    def test_approved_at_is_readonly(self):
        self.assertIn("approved_at", self.admin_instance.readonly_fields)


class EstimateAdminEstimatedTotalReadonlyTests(TestCase):
    def setUp(self):
        self.admin_instance = EstimateAdmin(Estimate, admin.site)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.request = make_request(make_user())

    def test_estimated_total_editable_without_line_items(self):
        estimate = Estimate.objects.create(repair_order=self.ro, estimate_number="EST-ADM-NOITEMS")
        readonly = self.admin_instance.get_readonly_fields(self.request, estimate)
        self.assertNotIn("estimated_total", readonly)

    def test_estimated_total_readonly_with_line_items(self):
        estimate = Estimate.objects.create(repair_order=self.ro, estimate_number="EST-ADM-ITEMS")
        EstimateLineItem.objects.create(
            estimate=estimate,
            item_type=EstimateLineItem.ItemType.LABOR,
            description="Paint",
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
        )
        readonly = self.admin_instance.get_readonly_fields(self.request, estimate)
        self.assertIn("estimated_total", readonly)

    def test_estimated_total_editable_on_add(self):
        readonly = self.admin_instance.get_readonly_fields(self.request, None)
        self.assertNotIn("estimated_total", readonly)


class EstimateLineItemInlinePermissionTests(TestCase):
    def setUp(self):
        self.inline = EstimateLineItemInline(Estimate, admin.site)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.request = make_request(make_user())

    def test_inline_allows_mutation_for_draft_estimate(self):
        estimate = Estimate.objects.create(repair_order=self.ro, estimate_number="EST-INL-DRAFT")
        self.assertTrue(self.inline.has_add_permission(self.request, estimate))
        self.assertTrue(self.inline.has_change_permission(self.request, estimate))
        self.assertTrue(self.inline.has_delete_permission(self.request, estimate))

    def test_inline_blocks_mutation_for_submitted_estimate(self):
        estimate = Estimate.objects.create(
            repair_order=self.ro, estimate_number="EST-INL-SUB", status=Estimate.Status.SUBMITTED
        )
        self.assertFalse(self.inline.has_add_permission(self.request, estimate))
        self.assertFalse(self.inline.has_change_permission(self.request, estimate))
        self.assertFalse(self.inline.has_delete_permission(self.request, estimate))

    def test_inline_allows_add_when_no_parent_yet(self):
        self.assertTrue(self.inline.has_add_permission(self.request, None))


class EstimateLineItemAdminEditableGuardTests(TestCase):
    def setUp(self):
        self.admin_instance = EstimateLineItemAdmin(EstimateLineItem, admin.site)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        # has_change_permission/has_delete_permission fall through to Django's
        # standard permission check when the estimate is editable, so use a
        # superuser here to isolate the draft-status gate under test.
        self.request = make_request(make_superuser())

    def test_change_permission_blocked_for_non_draft_estimate(self):
        estimate = Estimate.objects.create(
            repair_order=self.ro, estimate_number="EST-LI-PERM", status=Estimate.Status.SUBMITTED
        )
        item = EstimateLineItem.objects.create(
            estimate=estimate,
            item_type=EstimateLineItem.ItemType.LABOR,
            description="Paint",
            quantity=Decimal("1.00"),
            unit_price=Decimal("50.00"),
        )
        self.assertFalse(self.admin_instance.has_change_permission(self.request, item))
        self.assertFalse(self.admin_instance.has_delete_permission(self.request, item))

    def test_change_permission_allowed_for_draft_estimate(self):
        estimate = Estimate.objects.create(repair_order=self.ro, estimate_number="EST-LI-PERM-OK")
        item = EstimateLineItem.objects.create(
            estimate=estimate,
            item_type=EstimateLineItem.ItemType.LABOR,
            description="Paint",
            quantity=Decimal("1.00"),
            unit_price=Decimal("50.00"),
        )
        self.assertTrue(self.admin_instance.has_change_permission(self.request, item))
        self.assertTrue(self.admin_instance.has_delete_permission(self.request, item))

    def test_save_model_blocks_edit_for_non_draft_estimate(self):
        estimate = Estimate.objects.create(
            repair_order=self.ro, estimate_number="EST-LI-SAVE", status=Estimate.Status.SUBMITTED
        )
        item = EstimateLineItem.objects.create(
            estimate=estimate,
            item_type=EstimateLineItem.ItemType.LABOR,
            description="Paint",
            quantity=Decimal("1.00"),
            unit_price=Decimal("50.00"),
        )
        item.description = "Changed"
        self.admin_instance.save_model(self.request, item, None, change=True)
        item.refresh_from_db()
        self.assertEqual(item.description, "Paint")

    def test_save_model_allows_edit_for_draft_estimate(self):
        estimate = Estimate.objects.create(repair_order=self.ro, estimate_number="EST-LI-SAVE-OK")
        item = EstimateLineItem.objects.create(
            estimate=estimate,
            item_type=EstimateLineItem.ItemType.LABOR,
            description="Paint",
            quantity=Decimal("1.00"),
            unit_price=Decimal("50.00"),
        )
        item.description = "Changed"
        self.admin_instance.save_model(self.request, item, None, change=True)
        item.refresh_from_db()
        self.assertEqual(item.description, "Changed")
