from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.authorization import (
    ROLE_ESTIMATOR,
    ROLE_FRONT_DESK,
    ROLE_MANAGER,
    ROLE_READ_ONLY,
    ROLE_TECHNICIAN,
)
from billing.models import Invoice, InvoiceLineItem
from customers.models import Customer
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

VALID_VIN = "1HGBH41JXMN109186"
VALID_VIN_2 = "2T1BURHE0JC043821"


def assign_role(user, role_name):
    group, _created = Group.objects.get_or_create(name=role_name)
    user.groups.add(group)
    return user


def make_user(username, role_name=None):
    user = get_user_model().objects.create_user(
        username=username,
        password="pw-test-12345",
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


def make_repair_order(customer, vehicle, number="RO-AUTH-001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer,
        vehicle=vehicle,
        repair_order_number=number,
        **kwargs,
    )


def make_invoice(repair_order, number="INV-AUTH-001", **kwargs):
    defaults = {"subtotal": Decimal("200.00"), "tax_amount": Decimal("20.00")}
    defaults.update(kwargs)
    return Invoice.objects.create(
        repair_order=repair_order,
        invoice_number=number,
        **defaults,
    )


class ShopFacingAuthorizationTests(TestCase):
    def setUp(self):
        self.customer = make_customer()
        self.vehicle = make_vehicle(self.customer)
        self.ro = make_repair_order(self.customer, self.vehicle)
        self.invoice = make_invoice(self.ro)
        self.line_item = InvoiceLineItem.objects.create(
            invoice=self.invoice,
            item_type=InvoiceLineItem.ItemType.LABOR,
            description="Labor",
            quantity=Decimal("1.00"),
            unit_price=Decimal("50.00"),
        )

    def login_as(self, username, role_name=None):
        user = make_user(username, role_name)
        self.client.force_login(user)
        return user

    def test_dashboard_access(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/accounts/login/?next=/")

        self.login_as("no-role")
        self.assertEqual(self.client.get("/").status_code, 403)

        self.client.logout()
        self.login_as("read-only", ROLE_READ_ONLY)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_customer_permissions(self):
        self.login_as("readonly-customers", ROLE_READ_ONLY)

        self.assertEqual(self.client.get(reverse("customers:list")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("customers:detail", args=[self.customer.pk])).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse("customers:create")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("customers:edit", args=[self.customer.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("customers:vehicle_create", args=[self.customer.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("vehicles:edit", args=[self.vehicle.pk])).status_code,
            403,
        )

        self.client.logout()
        self.login_as("front-desk-customers", ROLE_FRONT_DESK)
        self.assertEqual(self.client.get(reverse("customers:create")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("customers:edit", args=[self.customer.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("customers:vehicle_create", args=[self.customer.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("vehicles:edit", args=[self.vehicle.pk])).status_code,
            200,
        )

    def test_repair_order_permissions(self):
        self.login_as("readonly-repair", ROLE_READ_ONLY)

        self.assertEqual(self.client.get(reverse("repair_orders:list")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("repair_orders:detail", args=[self.ro.pk])).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse("repair_orders:create")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("repair_orders:edit", args=[self.ro.pk])).status_code,
            403,
        )

        self.client.logout()
        technician = self.login_as("technician-repair", ROLE_TECHNICIAN)
        self.ro.assigned_to = technician
        self.ro.save(update_fields=["assigned_to", "updated_at"])
        self.assertEqual(self.client.get(reverse("repair_orders:list")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("repair_orders:detail", args=[self.ro.pk])).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse("repair_orders:create")).status_code, 403)
        self.assertEqual(
            self.client.get(reverse("repair_orders:edit", args=[self.ro.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("repair_orders:status_update", args=[self.ro.pk]),
                {"new_status": RepairOrder.Status.APPROVED, "note": "Nope"},
            ).status_code,
            403,
        )

        self.client.logout()
        self.login_as("estimator-repair", ROLE_ESTIMATOR)
        response = self.client.post(
            reverse("repair_orders:status_update", args=[self.ro.pk]),
            {"new_status": RepairOrder.Status.APPROVED, "note": "Allowed"},
        )
        self.assertRedirects(
            response,
            reverse("repair_orders:detail", args=[self.ro.pk]),
            fetch_redirect_response=False,
        )

    def test_billing_permissions(self):
        self.login_as("readonly-billing", ROLE_READ_ONLY)

        self.assertEqual(self.client.get(reverse("billing:invoice_list")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("billing:invoice_detail", args=[self.invoice.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("billing:invoice_create", args=[self.ro.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("billing:invoice_edit", args=[self.invoice.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("billing:invoice_issue", args=[self.invoice.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("billing:invoice_void", args=[self.invoice.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("billing:line_item_create", args=[self.invoice.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("billing:line_item_edit", args=[self.line_item.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("billing:payment_create", args=[self.invoice.pk])).status_code,
            403,
        )

        self.client.logout()
        self.login_as("front-desk-billing", ROLE_FRONT_DESK)
        self.assertEqual(
            self.client.get(reverse("billing:payment_create", args=[self.invoice.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(reverse("billing:invoice_issue", args=[self.invoice.pk])).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(reverse("billing:invoice_void", args=[self.invoice.pk])).status_code,
            403,
        )

        self.client.logout()
        self.login_as("manager-billing", ROLE_MANAGER)
        response = self.client.post(reverse("billing:invoice_issue", args=[self.invoice.pk]))
        self.assertRedirects(
            response,
            reverse("repair_orders:detail", args=[self.ro.pk]),
            fetch_redirect_response=False,
        )

    def test_front_desk_can_create_repair_orders_and_record_payments(self):
        self.login_as("front-desk-intake", ROLE_FRONT_DESK)

        self.assertEqual(self.client.get(reverse("repair_orders:create")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("billing:payment_create", args=[self.invoice.pk])).status_code,
            200,
        )

    def test_superuser_has_shop_facing_access_without_role_group(self):
        user = get_user_model().objects.create_superuser(
            username="super-shop",
            password="pw-test-12345",
        )
        self.client.force_login(user)

        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get(reverse("customers:create")).status_code, 200)
        self.assertEqual(self.client.get(reverse("repair_orders:create")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("billing:invoice_edit", args=[self.invoice.pk])).status_code,
            200,
        )
