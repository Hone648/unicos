from decimal import Decimal

from accounts.authorization import (
    ROLE_ESTIMATOR,
    ROLE_FRONT_DESK,
    ROLE_MANAGER,
    ROLE_OWNER_ADMIN,
    ROLE_READ_ONLY,
    ROLE_TECHNICIAN,
)
from accounts.policies import (
    can_change_repair_order_status,
    can_convert_estimate_to_invoice,
    can_edit_repair_order,
    can_manage_estimate,
    can_manage_invoice,
    can_manage_invoice_line_items,
    can_record_payment,
    can_view_estimate,
    can_view_invoice,
    can_view_repair_order,
    filter_repair_orders_for_user,
)
from billing.models import Invoice
from customers.models import Customer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from estimates.models import Estimate
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"


def assign_role(user, role_name):
    group, _created = Group.objects.get_or_create(name=role_name)
    user.groups.add(group)
    return user


def make_user(username, role_name=None, **kwargs):
    user = get_user_model().objects.create_user(
        username=username,
        password="pw-test-12345",
        **kwargs,
    )
    if role_name:
        assign_role(user, role_name)
    return user


def make_customer():
    return Customer.objects.create(
        customer_type=Customer.CustomerType.INDIVIDUAL,
        first_name="Policy",
        last_name="Tester",
    )


def make_vehicle(customer, vin=VALID_VIN):
    return Vehicle.objects.create(
        customer=customer,
        vin=vin,
        make="Honda",
        model="Civic",
        year=2021,
    )


def make_repair_order(customer, vehicle, number, **kwargs):
    return RepairOrder.objects.create(
        customer=customer,
        vehicle=vehicle,
        repair_order_number=number,
        **kwargs,
    )


def make_invoice(repair_order, number):
    return Invoice.objects.create(
        repair_order=repair_order,
        invoice_number=number,
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("0.00"),
    )


def make_estimate(repair_order, number):
    return Estimate.objects.create(
        repair_order=repair_order,
        estimate_number=number,
    )


class ObjectPolicyTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.other_vehicle = make_vehicle(self.customer, vin=VALID_VIN_2)
        self.technician = make_user("tech-policy", ROLE_TECHNICIAN)
        self.assigned_ro = make_repair_order(
            self.customer,
            self.vehicle,
            "RO-POLICY-ASSIGNED",
            assigned_to=self.technician,
        )
        self.unassigned_ro = make_repair_order(
            self.customer,
            self.other_vehicle,
            "RO-POLICY-OTHER",
        )
        self.invoice = make_invoice(self.assigned_ro, "INV-POLICY")
        self.estimate = make_estimate(self.assigned_ro, "EST-POLICY")

    def test_superuser_can_do_everything(self):
        user = make_user("policy-super", is_superuser=True, is_staff=True)
        self.assertTrue(can_view_repair_order(user, self.unassigned_ro))
        self.assertTrue(can_edit_repair_order(user, self.unassigned_ro))
        self.assertTrue(can_change_repair_order_status(user, self.unassigned_ro))
        self.assertTrue(can_view_estimate(user, self.estimate))
        self.assertTrue(can_manage_estimate(user, self.estimate))
        self.assertTrue(can_convert_estimate_to_invoice(user, self.estimate))
        self.assertTrue(can_view_invoice(user, self.invoice))
        self.assertTrue(can_manage_invoice(user, self.invoice))
        self.assertTrue(can_record_payment(user, self.invoice))
        self.assertTrue(can_manage_invoice_line_items(user, self.invoice))

    def test_owner_admin_can_manage_all_shop_objects(self):
        user = make_user("policy-owner", ROLE_OWNER_ADMIN)
        self.assertTrue(can_view_repair_order(user, self.unassigned_ro))
        self.assertTrue(can_edit_repair_order(user, self.unassigned_ro))
        self.assertTrue(can_change_repair_order_status(user, self.unassigned_ro))
        self.assertTrue(can_manage_invoice(user, self.invoice))

    def test_manager_can_manage_all_shop_objects(self):
        user = make_user("policy-manager", ROLE_MANAGER)
        self.assertTrue(can_view_repair_order(user, self.unassigned_ro))
        self.assertTrue(can_edit_repair_order(user, self.unassigned_ro))
        self.assertTrue(can_change_repair_order_status(user, self.unassigned_ro))
        self.assertTrue(can_manage_estimate(user, self.estimate))
        self.assertTrue(can_manage_invoice_line_items(user, self.invoice))

    def test_read_only_can_view_but_not_mutate(self):
        user = make_user("policy-readonly", ROLE_READ_ONLY)
        self.assertTrue(can_view_repair_order(user, self.unassigned_ro))
        self.assertTrue(can_view_invoice(user, self.invoice))
        self.assertFalse(can_edit_repair_order(user, self.unassigned_ro))
        self.assertFalse(can_change_repair_order_status(user, self.unassigned_ro))
        self.assertFalse(can_manage_invoice(user, self.invoice))
        self.assertFalse(can_record_payment(user, self.invoice))

    def test_technician_can_view_assigned_repair_order_only(self):
        self.assertTrue(can_view_repair_order(self.technician, self.assigned_ro))
        self.assertFalse(can_view_repair_order(self.technician, self.unassigned_ro))

    def test_technician_cannot_edit_assigned_repair_order(self):
        self.assertFalse(can_edit_repair_order(self.technician, self.assigned_ro))
        self.assertFalse(can_change_repair_order_status(self.technician, self.assigned_ro))

    def test_technician_queryset_is_limited_to_assigned_repair_orders(self):
        qs = filter_repair_orders_for_user(self.technician, RepairOrder.objects.all())
        self.assertIn(self.assigned_ro, qs)
        self.assertNotIn(self.unassigned_ro, qs)

    def test_manager_role_wins_for_multi_role_technician(self):
        assign_role(self.technician, ROLE_MANAGER)
        self.assertTrue(can_view_repair_order(self.technician, self.unassigned_ro))

    def test_front_desk_can_record_payment_but_not_manage_invoice(self):
        user = make_user("policy-front-desk", ROLE_FRONT_DESK)
        self.assertTrue(can_record_payment(user, self.invoice))
        self.assertFalse(can_manage_invoice(user, self.invoice))
        self.assertFalse(can_manage_invoice_line_items(user, self.invoice))

    def test_estimator_can_view_estimate_but_not_record_payment(self):
        user = make_user("policy-estimator", ROLE_ESTIMATOR)
        self.assertTrue(can_view_estimate(user, self.estimate))
        self.assertFalse(can_manage_estimate(user, self.estimate))
        self.assertFalse(can_record_payment(user, self.invoice))

    def test_billing_manage_user_can_manage_invoice_actions(self):
        user = make_user("policy-billing-manager", ROLE_MANAGER)
        self.assertTrue(can_manage_invoice(user, self.invoice))
        self.assertTrue(can_manage_invoice_line_items(user, self.invoice))
        self.assertTrue(can_convert_estimate_to_invoice(user, self.estimate))

    def test_billing_record_payment_user_cannot_issue_or_void(self):
        user = make_user("policy-payment-user", ROLE_FRONT_DESK)
        self.assertTrue(can_record_payment(user, self.invoice))
        self.assertFalse(can_manage_invoice(user, self.invoice))
