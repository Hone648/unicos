from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from customers.models import Customer
from estimates.models import Estimate, EstimateLineItem
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

    def test_has_approval_capture_false_without_metadata(self):
        estimate = make_estimate(
            self.ro,
            number="EST-NO-APP",
            status=Estimate.Status.APPROVED,
        )
        self.assertFalse(estimate.has_approval_capture)

    def test_has_approval_capture_true_with_required_metadata(self):
        estimate = make_estimate(
            self.ro,
            number="EST-HAS-APP",
            status=Estimate.Status.APPROVED,
            approval_source=Estimate.ApprovalSource.CUSTOMER,
            approval_contact_name="Jane Smith",
            approved_at=timezone.now(),
        )
        self.assertTrue(estimate.has_approval_capture)

    def test_repair_order_is_protected_from_delete_when_estimates_exist(self):
        from django.db.models import ProtectedError

        make_estimate(self.ro, number="EST-PROTECT")
        with self.assertRaises(ProtectedError):
            self.ro.delete()


def make_line_item(estimate, **kwargs):
    defaults = {
        "item_type": EstimateLineItem.ItemType.LABOR,
        "description": "Labor",
        "quantity": Decimal("1.00"),
        "unit_price": Decimal("100.00"),
    }
    defaults.update(kwargs)
    return EstimateLineItem.objects.create(estimate=estimate, **defaults)


# ---------------------------------------------------------------------------
# Supplement lineage
# ---------------------------------------------------------------------------

class EstimateSupplementTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.parent = make_estimate(self.ro, number="EST-PARENT")

    def test_default_kind_is_initial(self):
        self.assertEqual(self.parent.kind, Estimate.Kind.INITIAL)

    def test_initial_estimate_cannot_have_parent(self):
        bad = Estimate(
            repair_order=self.ro,
            estimate_number="EST-BAD-INIT",
            kind=Estimate.Kind.INITIAL,
            parent_estimate=self.parent,
        )
        with self.assertRaises(ValidationError):
            bad.full_clean()

    def test_supplement_requires_parent(self):
        bad = Estimate(
            repair_order=self.ro,
            estimate_number="EST-BAD-SUP",
            kind=Estimate.Kind.SUPPLEMENT,
            parent_estimate=None,
        )
        with self.assertRaises(ValidationError):
            bad.full_clean()

    def test_valid_supplement_passes_validation(self):
        supplement = Estimate(
            repair_order=self.ro,
            estimate_number="EST-SUP-OK",
            kind=Estimate.Kind.SUPPLEMENT,
            parent_estimate=self.parent,
        )
        supplement.full_clean()  # should not raise

    def test_supplement_parent_must_share_repair_order(self):
        other_customer = make_customer(first_name="Other")
        other_vehicle = make_vehicle(other_customer, vin=VALID_VIN_2)
        other_ro = make_repair_order(other_customer, other_vehicle, number="RO-OTHER")
        bad = Estimate(
            repair_order=other_ro,
            estimate_number="EST-CROSS-RO",
            kind=Estimate.Kind.SUPPLEMENT,
            parent_estimate=self.parent,
        )
        with self.assertRaises(ValidationError):
            bad.full_clean()

    def test_supplement_cannot_be_its_own_parent(self):
        supplement = make_estimate(
            self.ro,
            number="EST-SELF",
            kind=Estimate.Kind.SUPPLEMENT,
            parent_estimate=self.parent,
        )
        supplement.parent_estimate = supplement
        with self.assertRaises(ValidationError):
            supplement.full_clean()

    def test_parent_exposes_supplements_relation(self):
        make_estimate(
            self.ro, number="EST-SUP-1",
            kind=Estimate.Kind.SUPPLEMENT, parent_estimate=self.parent,
        )
        make_estimate(
            self.ro, number="EST-SUP-2",
            kind=Estimate.Kind.SUPPLEMENT, parent_estimate=self.parent,
        )
        self.assertEqual(self.parent.supplements.count(), 2)

    def test_parent_is_protected_from_delete_when_supplements_exist(self):
        from django.db.models import ProtectedError

        make_estimate(
            self.ro, number="EST-SUP-PROTECT",
            kind=Estimate.Kind.SUPPLEMENT, parent_estimate=self.parent,
        )
        with self.assertRaises(ProtectedError):
            self.parent.delete()


# ---------------------------------------------------------------------------
# Estimate line items
# ---------------------------------------------------------------------------

class EstimateLineItemModelTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.estimate = make_estimate(self.ro, number="EST-LI", estimated_total=Decimal("0.00"))

    def test_valid_line_item_can_be_created(self):
        item = make_line_item(self.estimate, quantity=Decimal("2.00"), unit_price=Decimal("50.00"))
        self.assertEqual(item.estimate, self.estimate)

    def test_line_total_computes_quantity_times_unit_price(self):
        item = make_line_item(self.estimate, quantity=Decimal("3.00"), unit_price=Decimal("25.00"))
        self.assertEqual(item.line_total, Decimal("75.00"))

    def test_quantity_zero_rejected(self):
        item = EstimateLineItem(
            estimate=self.estimate, description="x",
            quantity=Decimal("0.00"), unit_price=Decimal("10.00"),
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_quantity_negative_rejected(self):
        item = EstimateLineItem(
            estimate=self.estimate, description="x",
            quantity=Decimal("-1.00"), unit_price=Decimal("10.00"),
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_unit_price_negative_rejected(self):
        item = EstimateLineItem(
            estimate=self.estimate, description="x",
            quantity=Decimal("1.00"), unit_price=Decimal("-1.00"),
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_blank_description_rejected(self):
        item = EstimateLineItem(
            estimate=self.estimate, description="",
            quantity=Decimal("1.00"), unit_price=Decimal("10.00"),
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_whitespace_description_rejected(self):
        item = EstimateLineItem(
            estimate=self.estimate, description="   ",
            quantity=Decimal("1.00"), unit_price=Decimal("10.00"),
        )
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_zero_unit_price_allowed(self):
        item = make_line_item(self.estimate, unit_price=Decimal("0.00"))
        self.assertEqual(item.line_total, Decimal("0.00"))

    def test_saving_line_item_recalculates_estimate_total(self):
        make_line_item(self.estimate, quantity=Decimal("2.00"), unit_price=Decimal("75.00"))
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("150.00"))

    def test_editing_line_item_recalculates_total(self):
        item = make_line_item(self.estimate, quantity=Decimal("1.00"), unit_price=Decimal("100.00"))
        item.unit_price = Decimal("250.00")
        item.save()
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("250.00"))

    def test_deleting_line_item_recalculates_total(self):
        first = make_line_item(self.estimate, quantity=Decimal("1.00"), unit_price=Decimal("100.00"))
        make_line_item(self.estimate, quantity=Decimal("1.00"), unit_price=Decimal("40.00"))
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("140.00"))
        first.delete()
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("40.00"))

    def test_multiple_line_items_sum_correctly(self):
        make_line_item(self.estimate, quantity=Decimal("2.00"), unit_price=Decimal("50.00"))
        make_line_item(self.estimate, item_type=EstimateLineItem.ItemType.PARTS,
                       description="Bumper", quantity=Decimal("1.00"), unit_price=Decimal("300.00"))
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("400.00"))

    def test_deleting_all_line_items_resets_total_to_zero(self):
        item = make_line_item(self.estimate, quantity=Decimal("1.00"), unit_price=Decimal("100.00"))
        item.delete()
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("0.00"))

    def test_has_line_items_property(self):
        self.assertFalse(self.estimate.has_line_items)
        make_line_item(self.estimate)
        self.assertTrue(self.estimate.has_line_items)

    def test_str_includes_type_and_description(self):
        item = make_line_item(self.estimate, description="Refinish")
        self.assertEqual(str(item), "Labor: Refinish")
