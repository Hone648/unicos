from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.authorization import ROLE_MANAGER, ROLE_TECHNICIAN
from billing.models import Invoice, Payment
from customers.models import Customer
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle


def assign_role(user, role_name):
    group, _created = Group.objects.get_or_create(name=role_name)
    user.groups.add(group)
    return user


def make_user(username="dashboard-user", role_name=ROLE_MANAGER, **kwargs):
    user = get_user_model().objects.create_user(
        username=username, password="pw-test-12345", **kwargs
    )
    if role_name:
        assign_role(user, role_name)
    return user


def make_customer(first_name="Jane", last_name="Smith", **kwargs):
    defaults = {
        "customer_type": Customer.CustomerType.INDIVIDUAL,
        "first_name": first_name,
        "last_name": last_name,
    }
    defaults.update(kwargs)
    return Customer.objects.create(**defaults)


def vin_for(index):
    suffixes = "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"
    return f"1HGBH41JXMN10918{suffixes[index]}"


def make_vehicle(customer, index=0, **kwargs):
    defaults = {
        "vin": vin_for(index),
        "year": 2021,
        "make": "Honda",
        "model": "Civic",
    }
    defaults.update(kwargs)
    return Vehicle.objects.create(customer=customer, **defaults)


def make_repair_order(customer, vehicle, number="RO-DASH-001", **kwargs):
    return RepairOrder.objects.create(
        customer=customer,
        vehicle=vehicle,
        repair_order_number=number,
        **kwargs,
    )


def make_invoice(repair_order, number="INV-DASH-001", **kwargs):
    defaults = {
        "subtotal": Decimal("100.00"),
        "tax_amount": Decimal("10.00"),
    }
    defaults.update(kwargs)
    return Invoice.objects.create(
        repair_order=repair_order,
        invoice_number=number,
        **defaults,
    )


def make_payment(invoice, amount=Decimal("110.00"), **kwargs):
    defaults = {"payment_date": date.today(), "method": Payment.Method.CASH}
    defaults.update(kwargs)
    return Payment.objects.create(invoice=invoice, amount=amount, **defaults)


class DashboardWorkflowVisibilityTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.customer = make_customer()

    def _vehicle(self, index):
        return make_vehicle(self.customer, index=index)

    def _repair_order(self, number, index, status=RepairOrder.Status.INTAKE):
        return make_repair_order(
            self.customer,
            self._vehicle(index),
            number=number,
            status=status,
        )

    def test_counts_active_repair_orders_without_final_statuses(self):
        self._repair_order("RO-ACTIVE-1", 0, RepairOrder.Status.INTAKE)
        self._repair_order("RO-ACTIVE-2", 1, RepairOrder.Status.READY_FOR_PICKUP)
        self._repair_order("RO-DELIVERED", 2, RepairOrder.Status.DELIVERED)
        self._repair_order("RO-CLOSED", 3, RepairOrder.Status.CLOSED)
        self._repair_order("RO-CANCELED", 4, RepairOrder.Status.CANCELED)

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_repair_order_count"], 2)
        self.assertContains(response, "Active Repair Orders")
        self.assertContains(response, reverse("repair_orders:list"))

    def test_ready_for_pickup_count_list_link_and_empty_state(self):
        empty_response = self.client.get("/")
        self.assertEqual(empty_response.context["ready_for_pickup_count"], 0)
        self.assertContains(
            empty_response, "No ready-for-pickup repair orders."
        )

        ready = self._repair_order(
            "RO-READY", 0, RepairOrder.Status.READY_FOR_PICKUP
        )
        self._repair_order("RO-OTHER", 1, RepairOrder.Status.IN_REPAIR)

        response = self.client.get("/")

        self.assertEqual(response.context["ready_for_pickup_count"], 1)
        self.assertEqual(
            response.context["ready_for_pickup_repair_orders"],
            [ready],
        )
        self.assertContains(response, "RO-READY")
        self.assertContains(response, reverse("repair_orders:detail", args=[ready.pk]))
        self.assertContains(response, "?status=ready_for_pickup")

    def test_unpaid_invoice_count_total_list_link_and_empty_state(self):
        empty_response = self.client.get("/")
        self.assertEqual(empty_response.context["unpaid_invoice_count"], 0)
        self.assertContains(empty_response, "No unpaid invoices.")

        unpaid_ro = self._repair_order("RO-UNPAID", 0)
        unpaid = make_invoice(unpaid_ro, "INV-UNPAID")

        paid_ro = self._repair_order("RO-PAID", 1)
        paid = make_invoice(paid_ro, "INV-PAID")
        make_payment(paid)

        void_ro = self._repair_order("RO-VOID", 2)
        make_invoice(void_ro, "INV-VOID", status=Invoice.Status.VOID)

        response = self.client.get("/")

        self.assertEqual(response.context["unpaid_invoice_count"], 1)
        self.assertEqual(response.context["unpaid_invoice_total"], Decimal("110.00"))
        self.assertEqual(response.context["unpaid_invoices"], [unpaid])
        self.assertContains(response, "INV-UNPAID")
        self.assertContains(response, reverse("billing:invoice_list"))
        self.assertContains(response, reverse("billing:invoice_detail", args=[unpaid.pk]))
        self.assertNotContains(response, "INV-PAID")
        self.assertNotContains(response, "INV-VOID")

    def test_blocked_from_closure_count_list_link_and_empty_state(self):
        empty_response = self.client.get("/")
        self.assertEqual(empty_response.context["blocked_from_closure_count"], 0)
        self.assertContains(
            empty_response, "No repair orders blocked from closure."
        )

        blocked_ro = self._repair_order("RO-BLOCKED", 0, RepairOrder.Status.IN_REPAIR)
        blocked_invoice = make_invoice(blocked_ro, "INV-BLOCKED")

        final_ro = self._repair_order("RO-FINAL", 1, RepairOrder.Status.CLOSED)
        make_invoice(final_ro, "INV-FINAL")

        paid_ro = self._repair_order("RO-NOT-BLOCKED", 2, RepairOrder.Status.IN_REPAIR)
        paid_invoice = make_invoice(paid_ro, "INV-PAID")
        make_payment(paid_invoice)

        response = self.client.get("/")

        self.assertEqual(response.context["blocked_from_closure_count"], 1)
        self.assertEqual(
            response.context["blocked_from_closure_invoices"],
            [blocked_invoice],
        )
        self.assertContains(response, "RO-BLOCKED")
        self.assertContains(response, "INV-BLOCKED")
        self.assertContains(
            response, reverse("repair_orders:detail", args=[blocked_ro.pk])
        )

    def test_recently_updated_repair_orders_limit_and_order(self):
        orders = []
        now = timezone.now()
        for index in range(6):
            ro = self._repair_order(f"RO-RECENT-{index}", index)
            RepairOrder.objects.filter(pk=ro.pk).update(
                updated_at=now + timedelta(minutes=index)
            )
            orders.append(ro)

        response = self.client.get("/")

        recent_numbers = [
            ro.repair_order_number for ro in response.context["recent_repair_orders"]
        ]
        self.assertEqual(
            recent_numbers,
            [
                "RO-RECENT-5",
                "RO-RECENT-4",
                "RO-RECENT-3",
                "RO-RECENT-2",
                "RO-RECENT-1",
            ],
        )
        self.assertContains(response, "Recently Updated Repair Orders")
        self.assertContains(response, "RO-RECENT-5")
        self.assertNotContains(response, "RO-RECENT-0")

    def test_recently_updated_empty_state_and_existing_navigation_links_render(self):
        response = self.client.get("/")

        self.assertContains(response, "No recent repair orders.")
        self.assertContains(response, reverse("repair_orders:list"))
        self.assertContains(response, reverse("customers:list"))
        self.assertContains(response, reverse("billing:invoice_list"))
        self.assertContains(response, "Dashboard")


class TechnicianDashboardPermissionTests(TestCase):
    """Technician (repair_orders.view, no billing.view) sees no invoice numbers or amounts."""

    def setUp(self):
        self.user = make_user(username="tech-dash", role_name=ROLE_TECHNICIAN)
        self.client.force_login(self.user)
        self.customer = make_customer()
        vehicle = make_vehicle(self.customer, index=0)
        self.ro = make_repair_order(self.customer, vehicle, number="RO-TECH-001")
        # Invoice total = 110 (subtotal=100, tax=10), nothing paid → balance_due = 110
        self.invoice = make_invoice(self.ro, number="INV-TECH-001")

    def test_dashboard_loads_for_technician(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_technician_does_not_see_invoice_numbers_on_dashboard(self):
        response = self.client.get("/")
        self.assertNotContains(response, "INV-TECH-001")

    def test_technician_does_not_see_unpaid_invoices_card(self):
        response = self.client.get("/")
        self.assertNotContains(response, "Unpaid Invoices")

    def test_technician_sees_blocked_from_closure_section(self):
        response = self.client.get("/")
        self.assertContains(response, "Blocked From Closure")
        self.assertContains(response, "RO-TECH-001")

    def test_technician_does_not_see_invoice_number_in_blocked_card(self):
        response = self.client.get("/")
        self.assertNotContains(response, "INV-TECH-001")

    def test_technician_does_not_see_balance_due_hint(self):
        response = self.client.get("/")
        self.assertNotContains(response, "balance due")
        self.assertContains(response, "Open orders pending closure")
