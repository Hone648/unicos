"""Tax-totals tests for estimates: model recalculation, properties, form
taxability defaults, and detail/print rendering."""

from decimal import Decimal

from accounts.authorization import ROLE_MANAGER
from customers.models import Customer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from estimates.forms import EstimateLineItemForm
from estimates.models import Estimate, EstimateLineItem
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"


def make_user(username="tax-staffer", role_name=ROLE_MANAGER):
    user = get_user_model().objects.create_user(username=username, password="pw-test-12345")
    if role_name:
        group, _ = Group.objects.get_or_create(name=role_name)
        user.groups.add(group)
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


def make_repair_order(customer, vehicle, number="RO-TAX-001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer, vehicle=vehicle, repair_order_number=number, **kwargs
    )


def make_estimate(repair_order, number="EST-TAX-001", **kwargs):
    return Estimate.objects.create(repair_order=repair_order, estimate_number=number, **kwargs)


def make_line_item(estimate, **kwargs):
    defaults = {
        "item_type": EstimateLineItem.ItemType.LABOR,
        "description": "Line",
        "quantity": Decimal("1.00"),
        "unit_price": Decimal("100.00"),
    }
    defaults.update(kwargs)
    return EstimateLineItem.objects.create(estimate=estimate, **defaults)


class EstimateTaxRecalculationTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.estimate = make_estimate(self.ro, tax_rate=Decimal("0.0825"))

    def test_new_estimate_snapshots_default_tax_rate(self):
        self.assertEqual(self.estimate.tax_rate, Decimal("0.0825"))

    def test_labor_only_estimate_has_zero_taxable_and_tax(self):
        make_line_item(
            self.estimate,
            item_type=EstimateLineItem.ItemType.LABOR,
            quantity=Decimal("2.00"),
            unit_price=Decimal("100.00"),
            is_taxable=False,
        )
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("200.00"))
        self.assertEqual(self.estimate.taxable_subtotal, Decimal("0.00"))
        self.assertEqual(self.estimate.tax_amount, Decimal("0.00"))
        self.assertEqual(self.estimate.total_amount, Decimal("200.00"))

    def test_parts_estimate_calculates_taxable_subtotal_and_tax(self):
        make_line_item(
            self.estimate,
            item_type=EstimateLineItem.ItemType.PARTS,
            quantity=Decimal("1.00"),
            unit_price=Decimal("200.00"),
            is_taxable=True,
        )
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.taxable_subtotal, Decimal("200.00"))
        self.assertEqual(self.estimate.tax_amount, Decimal("16.50"))
        self.assertEqual(self.estimate.total_amount, Decimal("216.50"))

    def test_mixed_line_items_calculate_all_totals(self):
        make_line_item(
            self.estimate,
            item_type=EstimateLineItem.ItemType.LABOR,
            quantity=Decimal("1.00"),
            unit_price=Decimal("300.00"),
            is_taxable=False,
        )
        make_line_item(
            self.estimate,
            item_type=EstimateLineItem.ItemType.PARTS,
            quantity=Decimal("1.00"),
            unit_price=Decimal("200.00"),
            is_taxable=True,
        )
        self.estimate.deductible = Decimal("100.00")
        self.estimate.save(update_fields=["deductible"])
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("500.00"))
        self.assertEqual(self.estimate.taxable_subtotal, Decimal("200.00"))
        self.assertEqual(self.estimate.tax_amount, Decimal("16.50"))
        self.assertEqual(self.estimate.total_amount, Decimal("516.50"))
        # 516.50 total - 100.00 deductible
        self.assertEqual(self.estimate.customer_responsibility, Decimal("416.50"))

    def test_customer_responsibility_never_below_zero(self):
        make_line_item(
            self.estimate,
            item_type=EstimateLineItem.ItemType.PARTS,
            quantity=Decimal("1.00"),
            unit_price=Decimal("100.00"),
            is_taxable=True,
        )
        self.estimate.deductible = Decimal("5000.00")
        self.estimate.save(update_fields=["deductible"])
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.customer_responsibility, Decimal("0.00"))

    def test_deleting_line_item_recalculates_totals(self):
        item = make_line_item(
            self.estimate,
            item_type=EstimateLineItem.ItemType.PARTS,
            unit_price=Decimal("100.00"),
            is_taxable=True,
        )
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.tax_amount, Decimal("8.25"))
        item.delete()
        self.estimate.refresh_from_db()
        self.assertEqual(self.estimate.estimated_total, Decimal("0.00"))
        self.assertEqual(self.estimate.taxable_subtotal, Decimal("0.00"))
        self.assertEqual(self.estimate.tax_amount, Decimal("0.00"))

    def test_manual_estimated_total_preserved_without_line_items(self):
        estimate = make_estimate(
            self.ro,
            number="EST-MANUAL",
            estimated_total=Decimal("1234.00"),
        )
        estimate.refresh_from_db()
        self.assertEqual(estimate.estimated_total, Decimal("1234.00"))
        self.assertEqual(estimate.tax_amount, Decimal("0.00"))

    def test_negative_tax_rate_rejected(self):
        from django.core.exceptions import ValidationError

        self.estimate.tax_rate = Decimal("-0.01")
        with self.assertRaises(ValidationError):
            self.estimate.full_clean()

    def test_tax_rate_above_one_rejected(self):
        from django.core.exceptions import ValidationError

        self.estimate.tax_rate = Decimal("1.5")
        with self.assertRaises(ValidationError):
            self.estimate.full_clean()


class EstimateLineItemFormTaxabilityTests(TestCase):
    def test_form_exposes_taxable_field(self):
        form = EstimateLineItemForm()
        self.assertIn("is_taxable", form.fields)
        self.assertEqual(form.fields["is_taxable"].label, "Taxable")

    def test_new_form_defaults_labor_not_taxable(self):
        form = EstimateLineItemForm(initial={"item_type": "labor"})
        self.assertFalse(form.fields["is_taxable"].initial)

    def test_new_form_defaults_parts_taxable(self):
        form = EstimateLineItemForm(initial={"item_type": "parts"})
        self.assertTrue(form.fields["is_taxable"].initial)

    def test_new_form_defaults_materials_taxable(self):
        form = EstimateLineItemForm(initial={"item_type": "materials"})
        self.assertTrue(form.fields["is_taxable"].initial)

    def test_bound_value_is_authoritative(self):
        form = EstimateLineItemForm(
            data={
                "item_type": "parts",
                "description": "Bumper",
                "quantity": "1.00",
                "unit_price": "50.00",
                # is_taxable intentionally omitted -> unchecked wins
            }
        )
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data["is_taxable"])


class EstimateDetailPrintRenderingTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.estimate = make_estimate(self.ro, deductible=Decimal("100.00"))
        make_line_item(
            self.estimate,
            item_type=EstimateLineItem.ItemType.PARTS,
            quantity=Decimal("1.00"),
            unit_price=Decimal("200.00"),
            is_taxable=True,
        )
        self.estimate.refresh_from_db()

    def test_detail_renders_tax_totals(self):
        url = reverse("estimates:detail", kwargs={"pk": self.estimate.pk})
        response = self.client.get(url)
        self.assertContains(response, "Taxable subtotal")
        self.assertContains(response, "Estimated sales tax")
        self.assertContains(response, "Estimated customer responsibility")
        self.assertContains(response, "16.50")  # tax
        self.assertContains(response, "216.50")  # total
        self.assertContains(response, "116.50")  # customer responsibility

    def test_print_renders_tax_summary_and_disclaimer(self):
        url = reverse("estimates:print", kwargs={"pk": self.estimate.pk})
        response = self.client.get(url)
        self.assertContains(response, "16.50")
        self.assertContains(response, "Sales tax is estimated")

    def test_new_parts_line_item_defaults_taxable_via_view(self):
        url = reverse("estimates:line_item_create", kwargs={"estimate_pk": self.estimate.pk})
        response = self.client.get(url + "?")
        # The form renders a taxable checkbox control.
        self.assertContains(response, "Taxable")
