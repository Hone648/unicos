from datetime import timedelta

from accounts.authorization import (
    ROLE_ESTIMATOR,
    ROLE_FRONT_DESK,
    ROLE_MANAGER,
    ROLE_READ_ONLY,
    ROLE_TECHNICIAN,
)
from communications.forms import CommunicationEntryForm
from communications.models import CommunicationEntry
from customers.models import Customer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"


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


def make_repair_order(customer, vehicle, number="RO-COMM-001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number=number, **kwargs
    )


def make_entry(repair_order, **kwargs):
    defaults = {
        "occurred_at": timezone.now(),
        "direction": CommunicationEntry.Direction.OUTBOUND,
        "channel": CommunicationEntry.Channel.PHONE,
        "contact_role": CommunicationEntry.ContactRole.CUSTOMER,
        "contact_name": "Jane Smith",
        "summary": "Called with status update.",
    }
    defaults.update(kwargs)
    return CommunicationEntry.objects.create(repair_order=repair_order, **defaults)


def valid_form_data(**overrides):
    data = {
        "occurred_at": timezone.localtime(timezone.now()).strftime("%Y-%m-%dT%H:%M"),
        "direction": CommunicationEntry.Direction.OUTBOUND,
        "channel": CommunicationEntry.Channel.PHONE,
        "contact_role": CommunicationEntry.ContactRole.CUSTOMER,
        "contact_name": "Jane Smith",
        "summary": "Confirmed repair timing.",
        "next_step": "Call when parts arrive.",
        "is_authorization_related": "on",
    }
    data.update(overrides)
    return data


def create_url(repair_order_pk):
    return reverse("communications:create", kwargs={"repair_order_pk": repair_order_pk})


def detail_url(pk):
    return reverse("repair_orders:detail", kwargs={"pk": pk})


class CommunicationEntryFormTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_valid_communication_entry_saves(self):
        user = make_user()
        form = CommunicationEntryForm(data=valid_form_data())
        self.assertTrue(form.is_valid(), form.errors)

        entry = form.save(commit=False)
        entry.repair_order = self.ro
        entry.created_by = user
        entry.save()

        self.assertEqual(CommunicationEntry.objects.count(), 1)
        self.assertEqual(entry.contact_name, "Jane Smith")
        self.assertTrue(entry.is_authorization_related)

    def test_summary_blank_whitespace_rejected(self):
        form = CommunicationEntryForm(data=valid_form_data(summary="   "))

        self.assertFalse(form.is_valid())
        self.assertIn("summary", form.errors)

    def test_contact_name_required_for_inbound_and_outbound(self):
        for direction in (
            CommunicationEntry.Direction.INBOUND,
            CommunicationEntry.Direction.OUTBOUND,
        ):
            form = CommunicationEntryForm(
                data=valid_form_data(direction=direction, contact_name=" ")
            )
            self.assertFalse(form.is_valid(), f"Expected contact_name error for {direction}")
            self.assertIn("contact_name", form.errors)

    def test_contact_name_optional_for_internal(self):
        form = CommunicationEntryForm(
            data=valid_form_data(
                direction=CommunicationEntry.Direction.INTERNAL,
                contact_role=CommunicationEntry.ContactRole.SHOP_INTERNAL,
                contact_name="",
            )
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_occurred_at_far_future_rejected(self):
        future = timezone.localtime(timezone.now()) + timedelta(minutes=10)
        form = CommunicationEntryForm(
            data=valid_form_data(occurred_at=future.strftime("%Y-%m-%dT%H:%M"))
        )

        self.assertFalse(form.is_valid())
        self.assertIn("occurred_at", form.errors)

    def test_values_are_stripped_on_clean(self):
        form = CommunicationEntryForm(
            data=valid_form_data(
                contact_name="  Jane Smith  ",
                summary="  Confirmed repair timing.  ",
                next_step="  Follow up tomorrow.  ",
            )
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["contact_name"], "Jane Smith")
        self.assertEqual(form.cleaned_data["summary"], "Confirmed repair timing.")
        self.assertEqual(form.cleaned_data["next_step"], "Follow up tomorrow.")


class CommunicationCreateViewTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_unauthenticated_create_redirects_to_login(self):
        response = self.client.get(create_url(self.ro.pk))

        self.assertRedirects(response, f"/accounts/login/?next={create_url(self.ro.pk)}")

    def test_manager_can_create_and_redirects_to_detail(self):
        manager = make_user(username="comm-manager", role_name=ROLE_MANAGER)
        self.client.force_login(manager)

        response = self.client.post(create_url(self.ro.pk), data=valid_form_data())

        self.assertRedirects(response, detail_url(self.ro.pk))
        entry = CommunicationEntry.objects.get(repair_order=self.ro)
        self.assertEqual(entry.created_by, manager)
        self.assertEqual(entry.summary, "Confirmed repair timing.")

    def test_front_desk_can_create(self):
        user = make_user(username="comm-front-desk", role_name=ROLE_FRONT_DESK)
        self.client.force_login(user)

        response = self.client.post(create_url(self.ro.pk), data=valid_form_data())

        self.assertRedirects(response, detail_url(self.ro.pk))
        self.assertEqual(CommunicationEntry.objects.filter(repair_order=self.ro).count(), 1)

    def test_estimator_can_create(self):
        user = make_user(username="comm-estimator", role_name=ROLE_ESTIMATOR)
        self.client.force_login(user)

        response = self.client.post(create_url(self.ro.pk), data=valid_form_data())

        self.assertRedirects(response, detail_url(self.ro.pk))
        self.assertEqual(CommunicationEntry.objects.filter(repair_order=self.ro).count(), 1)

    def test_read_only_cannot_create(self):
        user = make_user(username="comm-read-only", role_name=ROLE_READ_ONLY)
        self.client.force_login(user)

        response = self.client.post(create_url(self.ro.pk), data=valid_form_data())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CommunicationEntry.objects.count(), 0)

    def test_assigned_technician_only_cannot_create(self):
        tech = make_user(username="comm-tech", role_name=ROLE_TECHNICIAN)
        self.ro.assigned_to = tech
        self.ro.save()
        self.client.force_login(tech)

        response = self.client.post(create_url(self.ro.pk), data=valid_form_data())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CommunicationEntry.objects.count(), 0)

    def test_user_without_repair_order_visibility_cannot_create_for_inaccessible_ro(self):
        tech = make_user(username="comm-unassigned-tech", role_name=ROLE_TECHNICIAN)
        self.client.force_login(tech)

        response = self.client.post(create_url(self.ro.pk), data=valid_form_data())

        self.assertEqual(response.status_code, 403)
        self.assertEqual(CommunicationEntry.objects.count(), 0)

    def test_invalid_post_renders_form_errors(self):
        manager = make_user(username="comm-manager-invalid", role_name=ROLE_MANAGER)
        self.client.force_login(manager)

        response = self.client.post(create_url(self.ro.pk), data=valid_form_data(summary=""))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Summary is required.")
        self.assertEqual(CommunicationEntry.objects.count(), 0)


class CommunicationRepairOrderDetailTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.entry = make_entry(
            self.ro,
            contact_name="Adjuster Amy",
            contact_role=CommunicationEntry.ContactRole.ADJUSTER,
            summary="Adjuster approved teardown photos.",
            next_step="Send supplement if needed.",
            is_authorization_related=True,
        )

    def test_entry_appears_on_repair_order_detail(self):
        user = make_user(username="comm-detail-manager", role_name=ROLE_MANAGER)
        self.client.force_login(user)

        response = self.client.get(detail_url(self.ro.pk))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Communication Log")
        self.assertContains(response, "Adjuster Amy")
        self.assertContains(response, "Adjuster approved teardown photos.")
        self.assertContains(response, "Add Communication")

    def test_assigned_technician_can_view_assigned_repair_order_communications(self):
        tech = make_user(username="comm-detail-tech", role_name=ROLE_TECHNICIAN)
        self.ro.assigned_to = tech
        self.ro.save()
        self.client.force_login(tech)

        response = self.client.get(detail_url(self.ro.pk))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Adjuster approved teardown photos.")
        self.assertNotContains(response, "Add Communication")

    def test_unassigned_technician_cannot_view_repair_order_communications(self):
        tech = make_user(username="comm-detail-unassigned-tech", role_name=ROLE_TECHNICIAN)
        self.client.force_login(tech)

        response = self.client.get(detail_url(self.ro.pk))

        self.assertEqual(response.status_code, 403)

    def test_read_only_can_view_but_cannot_add(self):
        user = make_user(username="comm-detail-read-only", role_name=ROLE_READ_ONLY)
        self.client.force_login(user)

        response = self.client.get(detail_url(self.ro.pk))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Adjuster approved teardown photos.")
        self.assertNotContains(response, "Add Communication")

    def test_detail_context_orders_latest_first_and_limits_to_ten(self):
        user = make_user(username="comm-detail-ordering", role_name=ROLE_MANAGER)
        self.client.force_login(user)
        self.entry.delete()
        base_time = timezone.now() - timedelta(days=1)
        for index in range(12):
            make_entry(
                self.ro,
                occurred_at=base_time + timedelta(minutes=index),
                contact_name=f"Contact {index}",
                summary=f"Entry {index}",
            )

        response = self.client.get(detail_url(self.ro.pk))

        self.assertEqual(response.status_code, 200)
        communications = list(response.context["communications"])
        self.assertEqual(len(communications), 10)
        self.assertEqual(communications[0].summary, "Entry 11")
        self.assertEqual(communications[-1].summary, "Entry 2")
        self.assertNotIn("Entry 1", {entry.summary for entry in communications})
