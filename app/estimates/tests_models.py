from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from customers.models import Customer
from estimates.models import Estimate
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"


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


def make_repair_order(customer, vehicle, number="RO-EST-001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number=number, **kwargs
    )


def make_estimate(repair_order, number="EST-001", **kwargs):
    return Estimate.objects.create(
        repair_order=repair_order, estimate_number=number, **kwargs
    )


class EstimateModelTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)

    def test_valid_estimate_can_be_created(self):
        estimate = make_estimate(
            self.ro,
            number="EST-VALID",
            insurance_company="Acme Insurance",
            claim_number="CLM-123",
            deductible=Decimal("500.00"),
            estimated_total=Decimal("2500.00"),
        )
        self.assertEqual(estimate.repair_order, self.ro)
        self.assertEqual(estimate.estimated_total, Decimal("2500.00"))

    def test_default_status_is_draft(self):
        estimate = make_estimate(self.ro, number="EST-DEFAULT")
        self.assertEqual(estimate.status, Estimate.Status.DRAFT)

    def test_default_deductible_and_total_are_zero(self):
        estimate = make_estimate(self.ro, number="EST-ZERO")
        self.assertEqual(estimate.deductible, Decimal("0.00"))
        self.assertEqual(estimate.estimated_total, Decimal("0.00"))

    def test_negative_deductible_is_rejected(self):
        estimate = Estimate(
            repair_order=self.ro,
            estimate_number="EST-NEG-DED",
            deductible=Decimal("-1.00"),
        )
        with self.assertRaises(ValidationError):
            estimate.full_clean()

    def test_negative_estimated_total_is_rejected(self):
        estimate = Estimate(
            repair_order=self.ro,
            estimate_number="EST-NEG-TOTAL",
            estimated_total=Decimal("-1.00"),
        )
        with self.assertRaises(ValidationError):
            estimate.full_clean()

    def test_repair_order_relation_exposes_estimates(self):
        make_estimate(self.ro, number="EST-REL-1")
        make_estimate(self.ro, number="EST-REL-2")
        self.assertEqual(self.ro.estimates.count(), 2)

    def test_multiple_estimates_per_repair_order_allowed(self):
        first = make_estimate(self.ro, number="EST-MULTI-1")
        second = make_estimate(self.ro, number="EST-MULTI-2")
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(
            set(self.ro.estimates.values_list("estimate_number", flat=True)),
            {"EST-MULTI-1", "EST-MULTI-2"},
        )

    def test_estimate_number_must_be_unique(self):
        make_estimate(self.ro, number="EST-DUP")
        with self.assertRaises(IntegrityError):
            make_estimate(self.ro, number="EST-DUP")

    def test_str_includes_estimate_number(self):
        estimate = make_estimate(self.ro, number="EST-STR")
        self.assertEqual(str(estimate), "Estimate EST-STR")

    def test_repair_order_is_protected_from_delete_when_estimates_exist(self):
        from django.db.models import ProtectedError

        make_estimate(self.ro, number="EST-PROTECT")
        with self.assertRaises(ProtectedError):
            self.ro.delete()
