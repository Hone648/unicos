from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from customers.models import Customer
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


def make_customer(first_name="Test", last_name="Customer", **kwargs):
    return Customer.objects.create(
        customer_type=Customer.CustomerType.INDIVIDUAL,
        first_name=first_name,
        last_name=last_name,
        **kwargs,
    )


def make_vehicle(customer, vin=VALID_VIN, **kwargs):
    return Vehicle.objects.create(
        customer=customer, vin=vin, make="Honda", model="Civic", year=2021, **kwargs
    )


def make_repair_order(customer, vehicle, number="RO-0001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer,
        vehicle=vehicle,
        repair_order_number=number,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# RepairOrder model tests
# ---------------------------------------------------------------------------

class RepairOrderModelTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)

    def test_can_create_repair_order_with_customer_and_vehicle(self):
        ro = make_repair_order(self.customer, self.vehicle)
        self.assertIsNotNone(ro.pk)
        self.assertEqual(ro.customer, self.customer)
        self.assertEqual(ro.vehicle, self.vehicle)

    def test_repair_order_number_is_unique(self):
        make_repair_order(self.customer, self.vehicle, number="RO-DUP")
        with self.assertRaises(IntegrityError):
            make_repair_order(self.customer, self.vehicle, number="RO-DUP")

    def test_str_includes_repair_order_number_and_vehicle(self):
        ro = make_repair_order(self.customer, self.vehicle)
        s = str(ro)
        self.assertIn("RO-0001", s)
        self.assertIn("Honda", s)

    def test_default_status_is_intake(self):
        ro = make_repair_order(self.customer, self.vehicle)
        self.assertEqual(ro.status, RepairOrder.Status.INTAKE)

    def test_assigned_staff_user_can_be_attached(self):
        user = make_user()
        ro = make_repair_order(self.customer, self.vehicle, assigned_to=user)
        self.assertEqual(ro.assigned_to, user)

    def test_created_by_and_updated_by_can_reference_user(self):
        user = make_user()
        ro = make_repair_order(
            self.customer, self.vehicle, created_by=user, updated_by=user
        )
        self.assertEqual(ro.created_by, user)
        self.assertEqual(ro.updated_by, user)

    def test_customer_deletion_protected_while_repair_orders_exist(self):
        make_repair_order(self.customer, self.vehicle)
        with self.assertRaises(ProtectedError):
            self.customer.delete()

    def test_vehicle_deletion_protected_while_repair_orders_exist(self):
        make_repair_order(self.customer, self.vehicle)
        with self.assertRaises(ProtectedError):
            self.vehicle.delete()

    def test_full_clean_fails_if_vehicle_belongs_to_different_customer(self):
        other_customer = make_customer(first_name="Other", last_name="Owner")
        # vehicle belongs to self.customer, but repair order claims other_customer
        ro = RepairOrder(
            repair_order_number="RO-MISMATCH",
            customer=other_customer,
            vehicle=self.vehicle,
        )
        with self.assertRaises(ValidationError):
            ro.full_clean()

    def test_full_clean_passes_if_vehicle_belongs_to_selected_customer(self):
        ro = RepairOrder(
            repair_order_number="RO-VALID",
            customer=self.customer,
            vehicle=self.vehicle,
        )
        ro.full_clean()  # should not raise


# ---------------------------------------------------------------------------
# Status history tests
# ---------------------------------------------------------------------------

class RepairOrderStatusHistoryTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)

    def test_creating_repair_order_creates_one_initial_history_row(self):
        ro = make_repair_order(self.customer, self.vehicle)
        self.assertEqual(ro.status_history.count(), 1)

    def test_initial_history_has_none_previous_status_and_intake_new_status(self):
        ro = make_repair_order(self.customer, self.vehicle)
        history = ro.status_history.first()
        self.assertIsNone(history.previous_status)
        self.assertEqual(history.new_status, RepairOrder.Status.INTAKE)

    def test_changing_status_creates_one_additional_history_row(self):
        ro = make_repair_order(self.customer, self.vehicle)
        ro.status = RepairOrder.Status.ESTIMATING
        ro.save()
        self.assertEqual(ro.status_history.count(), 2)

    def test_history_records_old_and_new_status_correctly(self):
        ro = make_repair_order(self.customer, self.vehicle)
        ro.status = RepairOrder.Status.ESTIMATING
        ro.save()
        # Newest-first ordering: index 0 is the status-change record
        latest = ro.status_history.first()
        self.assertEqual(latest.previous_status, RepairOrder.Status.INTAKE)
        self.assertEqual(latest.new_status, RepairOrder.Status.ESTIMATING)

    def test_saving_without_changing_status_does_not_create_duplicate_history(self):
        ro = make_repair_order(self.customer, self.vehicle)
        ro.internal_notes = "updated notes only"
        ro.save()
        self.assertEqual(ro.status_history.count(), 1)

    def test_set_status_updates_status_and_creates_history(self):
        ro = make_repair_order(self.customer, self.vehicle)
        ro.set_status(RepairOrder.Status.IN_REPAIR)
        ro.refresh_from_db()
        self.assertEqual(ro.status, RepairOrder.Status.IN_REPAIR)
        self.assertEqual(ro.status_history.count(), 2)

    def test_set_status_does_not_create_history_if_status_unchanged(self):
        ro = make_repair_order(self.customer, self.vehicle)
        ro.set_status(RepairOrder.Status.INTAKE)  # same as default
        self.assertEqual(ro.status_history.count(), 1)

    def test_set_status_records_changed_by(self):
        user = make_user()
        ro = make_repair_order(self.customer, self.vehicle)
        ro.set_status(RepairOrder.Status.APPROVED, changed_by=user)
        latest = ro.status_history.first()
        self.assertEqual(latest.changed_by, user)

    def test_set_status_records_note(self):
        ro = make_repair_order(self.customer, self.vehicle)
        ro.set_status(RepairOrder.Status.APPROVED, note="customer approved via phone")
        latest = ro.status_history.first()
        self.assertEqual(latest.note, "customer approved via phone")

    def test_status_history_ordering_is_newest_first(self):
        ro = make_repair_order(self.customer, self.vehicle)
        ro.set_status(RepairOrder.Status.ESTIMATING)
        ro.set_status(RepairOrder.Status.APPROVED)
        history = list(ro.status_history.all())
        # Newest first: APPROVED change should be at index 0
        self.assertEqual(history[0].new_status, RepairOrder.Status.APPROVED)
        self.assertEqual(history[-1].new_status, RepairOrder.Status.INTAKE)


# ---------------------------------------------------------------------------
# set_status validation and transient-attribute leak tests
# ---------------------------------------------------------------------------

class SetStatusValidationTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_set_status_rejects_invalid_status_with_validation_error(self):
        with self.assertRaises(ValidationError):
            self.ro.set_status("not_a_real_status")

    def test_invalid_set_status_does_not_change_repair_order_status(self):
        try:
            self.ro.set_status("bad_status")
        except ValidationError:
            pass
        self.assertEqual(self.ro.status, RepairOrder.Status.INTAKE)

    def test_invalid_set_status_does_not_create_history_row(self):
        try:
            self.ro.set_status("bad_status")
        except ValidationError:
            pass
        self.assertEqual(self.ro.status_history.count(), 1)

    def test_transient_note_does_not_leak_into_later_status_change(self):
        user = make_user()
        # First transition — has a note
        self.ro.set_status(RepairOrder.Status.ESTIMATING, changed_by=user, note="first note")
        # Second transition — no note
        self.ro.set_status(RepairOrder.Status.APPROVED)
        latest = self.ro.status_history.first()
        self.assertEqual(latest.note, "")

    def test_transient_changed_by_does_not_leak_into_later_status_change(self):
        user = make_user()
        # First transition — has a changed_by
        self.ro.set_status(RepairOrder.Status.ESTIMATING, changed_by=user)
        # Second transition — no changed_by provided
        self.ro.set_status(RepairOrder.Status.APPROVED)
        latest = self.ro.status_history.first()
        self.assertIsNone(latest.changed_by)
