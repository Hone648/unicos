from django.contrib.auth import get_user_model
from django.test import TestCase

from customers.models import Customer
from estimates.models import Estimate
from estimates.services import (
    EstimateStatusTransitionBlocked,
    estimate_is_editable,
    get_available_estimate_status_transitions,
    transition_estimate_status,
)
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


def approval_data(**overrides):
    data = {
        "approval_source": Estimate.ApprovalSource.CUSTOMER,
        "approval_contact_name": "Jane Smith",
        "approval_reference": "EMAIL-123",
        "approval_note": "Approved by email.",
    }
    data.update(overrides)
    return data


def make_estimate(status=Estimate.Status.DRAFT, number="EST-SERVICE"):
    customer = Customer.objects.create(
        customer_type=Customer.CustomerType.INDIVIDUAL,
        first_name="Service",
        last_name="Test",
    )
    vehicle = Vehicle.objects.create(
        customer=customer,
        vin=VALID_VIN,
        make="Honda",
        model="Civic",
        year=2021,
    )
    ro = RepairOrder.objects.create(
        customer=customer,
        vehicle=vehicle,
        repair_order_number=f"RO-{number}",
    )
    return Estimate.objects.create(
        repair_order=ro,
        estimate_number=number,
        status=status,
    )


class EstimateStatusTransitionServiceTests(TestCase):
    def test_draft_to_submitted_succeeds(self):
        estimate = make_estimate()
        transition_estimate_status(estimate, Estimate.Status.SUBMITTED)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.SUBMITTED)

    def test_submitted_to_approved_succeeds(self):
        estimate = make_estimate(status=Estimate.Status.SUBMITTED)
        transition_estimate_status(
            estimate,
            Estimate.Status.APPROVED,
            approval_data=approval_data(),
        )
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.APPROVED)

    def test_submitted_to_approved_requires_approval_data(self):
        estimate = make_estimate(status=Estimate.Status.SUBMITTED)
        with self.assertRaises(EstimateStatusTransitionBlocked):
            transition_estimate_status(estimate, Estimate.Status.APPROVED)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.SUBMITTED)
        self.assertEqual(estimate.approval_source, "")
        self.assertEqual(estimate.approval_contact_name, "")
        self.assertIsNone(estimate.approved_at)

    def test_submitted_to_approved_rejects_invalid_approval_source(self):
        estimate = make_estimate(status=Estimate.Status.SUBMITTED)
        with self.assertRaises(EstimateStatusTransitionBlocked):
            transition_estimate_status(
                estimate,
                Estimate.Status.APPROVED,
                approval_data=approval_data(approval_source="bad-source"),
            )
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.SUBMITTED)
        self.assertEqual(estimate.approval_source, "")

    def test_submitted_to_approved_stores_approval_capture(self):
        estimate = make_estimate(status=Estimate.Status.SUBMITTED)
        transition_estimate_status(
            estimate,
            Estimate.Status.APPROVED,
            approval_data=approval_data(
                approval_contact_name="  Jane Smith  ",
                approval_reference="  REF-99  ",
                approval_note="  Approved by phone.  ",
            ),
        )
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.APPROVED)
        self.assertEqual(estimate.approval_source, Estimate.ApprovalSource.CUSTOMER)
        self.assertEqual(estimate.approval_contact_name, "Jane Smith")
        self.assertEqual(estimate.approval_reference, "REF-99")
        self.assertEqual(estimate.approval_note, "Approved by phone.")
        self.assertIsNotNone(estimate.approved_at)

    def test_submitted_to_declined_succeeds(self):
        estimate = make_estimate(status=Estimate.Status.SUBMITTED)
        transition_estimate_status(estimate, Estimate.Status.DECLINED)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.DECLINED)

    def test_submitted_to_expired_succeeds(self):
        estimate = make_estimate(status=Estimate.Status.SUBMITTED)
        transition_estimate_status(estimate, Estimate.Status.EXPIRED)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.EXPIRED)

    def test_draft_to_approved_is_blocked(self):
        estimate = make_estimate()
        with self.assertRaises(EstimateStatusTransitionBlocked):
            transition_estimate_status(estimate, Estimate.Status.APPROVED)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.DRAFT)

    def test_approved_to_submitted_is_blocked(self):
        estimate = make_estimate(status=Estimate.Status.APPROVED)
        with self.assertRaises(EstimateStatusTransitionBlocked):
            transition_estimate_status(estimate, Estimate.Status.SUBMITTED)
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.APPROVED)

    def test_invalid_status_is_blocked(self):
        estimate = make_estimate()
        with self.assertRaises(EstimateStatusTransitionBlocked):
            transition_estimate_status(estimate, "not-a-status")
        estimate.refresh_from_db()
        self.assertEqual(estimate.status, Estimate.Status.DRAFT)

    def test_updated_by_is_set_when_provided(self):
        user = get_user_model().objects.create_user(
            username="estimate-transition-user",
            password="pw-test-12345",
        )
        estimate = make_estimate()
        transition_estimate_status(
            estimate,
            Estimate.Status.SUBMITTED,
            updated_by=user,
        )
        estimate.refresh_from_db()
        self.assertEqual(estimate.updated_by, user)

    def test_get_available_transitions_for_draft(self):
        estimate = make_estimate()
        self.assertEqual(
            get_available_estimate_status_transitions(estimate),
            {Estimate.Status.SUBMITTED},
        )

    def test_terminal_estimate_is_not_editable(self):
        estimate = make_estimate(status=Estimate.Status.APPROVED)
        self.assertFalse(estimate_is_editable(estimate))
