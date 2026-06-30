from datetime import date
from decimal import Decimal

from accounts.authorization import (
    ROLE_ESTIMATOR,
    ROLE_FRONT_DESK,
    ROLE_MANAGER,
    ROLE_OWNER_ADMIN,
    ROLE_READ_ONLY,
    ROLE_TECHNICIAN,
)
from billing.models import Invoice, Payment
from customers.models import Customer
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from estimates.models import Estimate
from repair_orders.models import RepairOrder
from vehicles.models import Vehicle

REPORTS_URL = reverse("reports")


def assign_role(user, role_name):
    group, _created = Group.objects.get_or_create(name=role_name)
    user.groups.add(group)
    return user


def make_user(username="reports-user", role_name=ROLE_MANAGER, **kwargs):
    user = get_user_model().objects.create_user(
        username=username,
        password="pw-test-12345",
        **kwargs,
    )
    if role_name:
        assign_role(user, role_name)
    return user


def make_customer(first_name="Robin", last_name="Reports", **kwargs):
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
        "year": 2022,
        "make": "Toyota",
        "model": "Camry",
    }
    defaults.update(kwargs)
    return Vehicle.objects.create(customer=customer, **defaults)


def make_repair_order(customer, vehicle, number, **kwargs):
    return RepairOrder.objects.create(
        customer=customer,
        vehicle=vehicle,
        repair_order_number=number,
        **kwargs,
    )


def make_invoice(repair_order, number, **kwargs):
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


def make_payment(invoice, amount, **kwargs):
    defaults = {"payment_date": date.today(), "method": Payment.Method.CASH}
    defaults.update(kwargs)
    return Payment.objects.create(invoice=invoice, amount=amount, **defaults)


def make_estimate(repair_order, number, **kwargs):
    defaults = {
        "estimated_total": Decimal("100.00"),
    }
    defaults.update(kwargs)
    return Estimate.objects.create(
        repair_order=repair_order,
        estimate_number=number,
        **defaults,
    )


class ReportsAccessTests(TestCase):
    def test_unauthenticated_reports_redirects_to_login(self):
        response = self.client.get(REPORTS_URL)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/accounts/login/?next=/reports/")

    def test_authorized_roles_can_access_reports(self):
        allowed_roles = [
            ROLE_OWNER_ADMIN,
            ROLE_MANAGER,
            ROLE_READ_ONLY,
        ]

        for index, role_name in enumerate(allowed_roles):
            with self.subTest(role_name=role_name):
                user = make_user(username=f"reports-allowed-{index}", role_name=role_name)
                self.client.force_login(user)

                response = self.client.get(REPORTS_URL)

                self.assertEqual(response.status_code, 200)
                self.client.logout()

    def test_superuser_can_access_reports(self):
        user = get_user_model().objects.create_superuser(
            username="reports-super",
            password="pw-test-12345",
        )
        self.client.force_login(user)

        response = self.client.get(REPORTS_URL)

        self.assertEqual(response.status_code, 200)

    def test_unauthorized_roles_receive_forbidden(self):
        denied_roles = [
            ROLE_FRONT_DESK,
            ROLE_ESTIMATOR,
            ROLE_TECHNICIAN,
        ]

        for index, role_name in enumerate(denied_roles):
            with self.subTest(role_name=role_name):
                user = make_user(username=f"reports-denied-{index}", role_name=role_name)
                self.client.force_login(user)

                response = self.client.get(REPORTS_URL)

                self.assertEqual(response.status_code, 403)
                self.client.logout()

    def test_reports_nav_link_requires_reports_permission(self):
        read_only = make_user(username="reports-nav-readonly", role_name=ROLE_READ_ONLY)
        self.client.force_login(read_only)

        response = self.client.get(REPORTS_URL)

        self.assertContains(response, f'href="{REPORTS_URL}"')
        self.client.logout()

        technician = make_user(username="reports-nav-tech", role_name=ROLE_TECHNICIAN)
        self.client.force_login(technician)

        response = self.client.get("/")

        self.assertNotContains(response, f'href="{REPORTS_URL}"')


class ReportsContentTests(TestCase):
    def setUp(self):
        self.user = make_user(username="reports-manager", role_name=ROLE_MANAGER)
        self.client.force_login(self.user)
        self.customer = make_customer()
        self.vehicle_index = 0

    def _repair_order(self, number, **kwargs):
        self.vehicle_index += 1
        defaults = {"assigned_to": self.user}
        defaults.update(kwargs)
        return make_repair_order(
            self.customer,
            make_vehicle(self.customer, index=self.vehicle_index),
            number,
            **defaults,
        )

    def test_reports_metrics_and_links(self):
        self._repair_order(
            "RO-REPORT-ACTIVE",
            status=RepairOrder.Status.IN_REPAIR,
            assigned_to=None,
        )
        ready_ro = self._repair_order(
            "RO-REPORT-READY",
            status=RepairOrder.Status.READY_FOR_PICKUP,
            promised_date=date(2026, 7, 15),
        )
        self._repair_order("RO-REPORT-CLOSED", status=RepairOrder.Status.CLOSED)

        draft_invoice = make_invoice(
            self._repair_order("RO-REPORT-DRAFT-INVOICE"),
            "INV-REPORT-DRAFT",
        )
        partial_invoice = make_invoice(
            self._repair_order("RO-REPORT-PARTIAL-INVOICE"),
            "INV-REPORT-PARTIAL",
            status=Invoice.Status.ISSUED,
            subtotal=Decimal("200.00"),
            tax_amount=Decimal("0.00"),
        )
        make_payment(partial_invoice, Decimal("50.00"))
        partial_invoice.refresh_from_db()

        paid_invoice = make_invoice(
            self._repair_order("RO-REPORT-PAID-INVOICE"),
            "INV-REPORT-PAID",
        )
        make_payment(paid_invoice, Decimal("110.00"))
        paid_invoice.refresh_from_db()

        make_invoice(
            self._repair_order("RO-REPORT-VOID-INVOICE"),
            "INV-REPORT-VOID",
            status=Invoice.Status.VOID,
        )

        draft_estimate = make_estimate(
            self._repair_order("RO-REPORT-DRAFT-ESTIMATE"),
            "EST-REPORT-DRAFT",
            status=Estimate.Status.DRAFT,
        )
        submitted_estimate = make_estimate(
            self._repair_order("RO-REPORT-SUBMITTED-ESTIMATE"),
            "EST-REPORT-SUBMITTED",
            status=Estimate.Status.SUBMITTED,
        )
        converted_estimate = make_estimate(
            self._repair_order("RO-REPORT-CONVERTED-ESTIMATE"),
            "EST-REPORT-CONVERTED",
            status=Estimate.Status.APPROVED,
            approval_source=Estimate.ApprovalSource.CUSTOMER,
            approval_contact_name="Robin Reports",
            approved_at=timezone.now(),
        )
        make_invoice(
            converted_estimate.repair_order,
            "INV-REPORT-CONVERTED",
            source_estimate=converted_estimate,
        )
        missing_capture_estimate = make_estimate(
            self._repair_order("RO-REPORT-MISSING-CAPTURE"),
            "EST-REPORT-MISSING-CAPTURE",
            status=Estimate.Status.APPROVED,
        )

        response = self.client.get(REPORTS_URL)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_repair_order_count"], 10)
        self.assertEqual(response.context["ready_for_pickup_count"], 1)
        self.assertEqual(response.context["final_repair_order_count"], 1)
        self.assertEqual(response.context["unassigned_active_repair_order_count"], 1)
        self.assertEqual(response.context["ready_for_pickup_repair_orders"], [ready_ro])
        self.assertEqual(response.context["non_void_invoice_count"], 4)
        self.assertEqual(response.context["unpaid_invoice_count"], 3)
        self.assertEqual(response.context["total_balance_due"], Decimal("370.00"))
        self.assertEqual(response.context["draft_invoice_count"], 2)
        self.assertEqual(response.context["issued_or_partially_paid_invoice_count"], 1)
        self.assertEqual(response.context["paid_invoice_count"], 1)
        self.assertEqual(response.context["void_invoice_count"], 1)
        self.assertEqual(response.context["draft_estimate_count"], 1)
        self.assertEqual(response.context["submitted_estimate_count"], 1)
        self.assertEqual(response.context["approved_estimate_count"], 2)
        self.assertEqual(response.context["approved_with_capture_count"], 1)
        self.assertEqual(response.context["approved_missing_capture_count"], 1)
        self.assertEqual(response.context["approved_converted_count"], 1)
        self.assertEqual(response.context["approved_not_converted_count"], 1)

        attention_estimates = [
            row["estimate"] for row in response.context["estimates_needing_attention"]
        ]
        self.assertIn(submitted_estimate, attention_estimates)
        self.assertIn(missing_capture_estimate, attention_estimates)
        self.assertNotIn(draft_estimate, attention_estimates)
        self.assertNotIn(converted_estimate, attention_estimates)

        self.assertContains(response, "Reports")
        self.assertContains(
            response,
            "Read-only operational snapshot. Exports, charts, date ranges, "
            "and deeper analytics are future work.",
        )
        self.assertContains(response, reverse("billing:invoice_detail", args=[draft_invoice.pk]))
        self.assertContains(response, reverse("repair_orders:detail", args=[ready_ro.pk]))
        self.assertContains(response, reverse("estimates:detail", args=[submitted_estimate.pk]))
