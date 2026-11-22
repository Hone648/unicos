from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from accounts.authorization import (
    ROLE_ESTIMATOR,
    ROLE_FRONT_DESK,
    ROLE_MANAGER,
    ROLE_READ_ONLY,
    ROLE_TECHNICIAN,
)
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from estimates.models import Estimate
from repair_orders.models import RepairOrder, RepairOrderStatusHistory
from repair_orders.services import (
    RepairOrderStatusTransitionBlocked,
    transition_repair_order_status,
)
from repair_orders.status_continuation import sign_status_continuation
from repair_orders.tests_views import (
    detail_url,
    make_customer,
    make_invoice,
    make_payment,
    make_repair_order,
    make_user,
    make_vehicle,
    status_url,
)


class IntakeNextActionTests(TestCase):
    def setUp(self):
        self.manager = make_user()
        self.client.force_login(self.manager)
        customer = make_customer()
        self.ro = make_repair_order(customer, make_vehicle(customer))
        self.estimate_url = reverse("estimates:create", kwargs={"repair_order_pk": self.ro.pk})

    def test_fresh_intake_has_one_primary_estimate_action_before_secondary_status_controls(self):
        response = self.client.get(detail_url(self.ro.pk))
        self.assertTrue(response.context["show_intake_estimate_action"])
        self.assertContains(response, f'href="{self.estimate_url}"', count=1)
        self.assertContains(
            response,
            f'<a class="btn btn-primary" href="{self.estimate_url}">Create Estimate</a>',
            html=True,
        )
        self.assertContains(
            response,
            '<button class="btn btn-outline-secondary" type="submit">Update Status</button>',
            html=True,
        )
        status_section = response.content.decode().split('id="job-status-heading"')[1]
        self.assertLess(
            status_section.index(self.estimate_url), status_section.index('id="new_status"')
        )

    def test_action_uses_estimate_permission_even_without_status_permission(self):
        for role, permitted in [
            (ROLE_MANAGER, True),
            (ROLE_FRONT_DESK, True),
            (ROLE_ESTIMATOR, False),
            (ROLE_READ_ONLY, False),
            (ROLE_TECHNICIAN, False),
        ]:
            with self.subTest(role=role):
                user = make_user(username=f"next-{role}", role_name=role)
                self.ro.assigned_to = user
                self.ro.save()
                self.client.force_login(user)
                response = self.client.get(detail_url(self.ro.pk))
                self.assertEqual(response.context["show_intake_estimate_action"], permitted)
                if permitted:
                    self.assertContains(response, f'href="{self.estimate_url}"', count=1)
                else:
                    self.assertNotContains(response, self.estimate_url)
                if role == ROLE_FRONT_DESK:
                    self.assertNotContains(response, 'id="status-update-card"')

    def test_other_states_keep_the_estimate_action_in_estimates(self):
        for status in RepairOrder.Status.values:
            if status == RepairOrder.Status.INTAKE:
                continue
            with self.subTest(status=status):
                RepairOrder.objects.filter(pk=self.ro.pk).update(status=status)
                response = self.client.get(detail_url(self.ro.pk))
                self.assertFalse(response.context["show_intake_estimate_action"])
                self.assertContains(response, f'href="{self.estimate_url}"', count=1)
                billing = response.content.decode().split('id="job-billing-heading"')[1]
                self.assertIn(self.estimate_url, billing)

    def test_intake_with_an_estimate_keeps_existing_estimate_actions(self):
        Estimate.objects.create(repair_order=self.ro, estimate_number="EST-NEXT-EXISTS")
        response = self.client.get(detail_url(self.ro.pk))
        self.assertFalse(response.context["show_intake_estimate_action"])
        self.assertContains(response, f'href="{self.estimate_url}"', count=1)
        self.assertContains(response, "EST-NEXT-EXISTS")
        self.assertIn(
            self.estimate_url,
            response.content.decode().split('id="job-billing-heading"')[1],
        )

    def test_htmx_moves_the_single_action_when_entering_and_leaving_intake(self):
        self.ro.set_status(RepairOrder.Status.ESTIMATING)
        for status, prominent in [("intake", True), ("estimating", False)]:
            with self.subTest(status=status):
                response = self.client.post(
                    status_url(self.ro.pk), {"new_status": status}, HTTP_HX_REQUEST="true"
                )
                self.assertEqual(response.context["show_intake_estimate_action"], prominent)
                self.assertContains(response, f'href="{self.estimate_url}"', count=1)
                self.assertContains(response, 'id="ro-next-action" hx-swap-oob="true"', count=1)
                self.assertContains(response, 'id="ro-estimate-action"', count=1)
                self.assertContains(response, 'hx-target="#status-update-card"')
                detail = self.client.get(detail_url(self.ro.pk))
                self.assertContains(detail, f'href="{self.estimate_url}"', count=1)

    def test_balance_warning_takes_priority_over_the_intake_action(self):
        make_invoice(self.ro, subtotal=Decimal("100.00"), tax_amount=Decimal("0.00"))
        response = self.client.post(
            status_url(self.ro.pk), {"new_status": "closed"}, HTTP_HX_REQUEST="true"
        )
        self.assertFalse(response.context["show_intake_estimate_action"])
        self.assertContains(response, '<a class="btn btn-primary"', count=1)
        self.assertContains(response, "Record payment")
        self.assertContains(response, f'href="{self.estimate_url}"', count=1)

    def test_valid_continuation_has_priority_even_after_balance_is_paid(self):
        invoice = make_invoice(self.ro)
        make_payment(invoice, Decimal("440.00"))
        for recorded in (False, True):
            with self.subTest(payment_recorded=recorded):
                token = sign_status_continuation(invoice, "closed", payment_recorded=recorded)
                response = self.client.get(detail_url(self.ro.pk), {"status_continuation": token})
                self.assertFalse(response.context["show_intake_estimate_action"])
                self.assertContains(
                    response,
                    '<button class="btn btn-primary" type="submit">Update Status</button>',
                    html=True,
                )
                self.assertContains(response, f'href="{self.estimate_url}"', count=1)

    def test_invalid_continuation_does_not_hide_the_intake_next_action(self):
        invoice = make_invoice(self.ro)
        token = sign_status_continuation(invoice, "closed") + "tampered"
        response = self.client.get(detail_url(self.ro.pk), {"status_continuation": token})
        self.assertTrue(response.context["show_intake_estimate_action"])


class PaymentNextStepTests(TestCase):
    def setUp(self):
        self.manager = make_user()
        self.client.force_login(self.manager)
        customer = make_customer()
        self.ro = make_repair_order(customer, make_vehicle(customer))
        self.invoice = make_invoice(self.ro, subtotal=Decimal("100.00"), tax_amount=Decimal("0.00"))
        self.payment_url = reverse("billing:payment_create", kwargs={"invoice_pk": self.invoice.pk})

    def test_full_payment_prompt_matches_requested_status_without_applying_it(self):
        actions = {
            "closed": "close this repair order",
            "delivered": "mark this repair order as delivered",
            "canceled": "cancel this repair order",
        }
        for target, action in actions.items():
            with self.subTest(target=target):
                self.invoice.payments.all().delete()
                self.invoice.sync_payment_status()
                token = sign_status_continuation(self.invoice, target)
                response = self.client.post(
                    self.payment_url,
                    {
                        "status_continuation": token,
                        "payment_date": "2026-11-22",
                        "amount": "100.00",
                        "method": "cash",
                    },
                    follow=True,
                )
                prompt = f"Invoice paid in full. Select Update Status to {action}."
                self.assertContains(response, prompt)
                self.assertEqual(response.context["selected_status"], target)
                self.assertEqual(
                    urlsplit(response.redirect_chain[-1][0]).fragment, "status-update-card"
                )
                self.assertFalse(response.context["show_intake_estimate_action"])
                self.ro.refresh_from_db()
                self.assertEqual(self.ro.status, RepairOrder.Status.INTAKE)
                self.assertIsNone(self.ro.closed_at)
                self.assertEqual(self.ro.status_history.count(), 1)

    def test_partial_payment_then_final_payment_requires_explicit_closure(self):
        token = sign_status_continuation(self.invoice, "closed")
        for amount, balance in [("40.00", "60.00"), ("60.00", "0.00")]:
            response = self.client.post(
                self.payment_url,
                {
                    "status_continuation": token,
                    "payment_date": "2026-11-22",
                    "amount": amount,
                    "method": "cash",
                },
                follow=True,
            )
            self.ro.refresh_from_db()
            self.assertEqual(self.ro.status, RepairOrder.Status.INTAKE)
            self.assertIsNone(self.ro.closed_at)
            self.assertEqual(response.context["selected_status"], "closed")
            if balance != "0.00":
                self.assertContains(response, "has a remaining balance of $60.00.")
                self.assertContains(response, "Record another payment")
                self.assertNotContains(response, "Select Update Status to close")
            else:
                self.assertContains(
                    response,
                    "Invoice paid in full. Select Update Status to close this repair order.",
                )
                self.assertNotContains(response, "Record another payment")
            token = parse_qs(urlsplit(response.redirect_chain[-1][0]).query)["status_continuation"][
                0
            ]
        self.client.post(status_url(self.ro.pk), {"new_status": "closed"})
        self.ro.refresh_from_db()
        self.assertIsNotNone(self.ro.closed_at)
        stale = self.client.get(detail_url(self.ro.pk), {"status_continuation": token})
        self.assertNotContains(stale, "Invoice paid in full. Select Update Status")
        self.assertEqual(self.invoice.payments.count(), 2)


class ClosedDateTransitionTests(TestCase):
    def setUp(self):
        customer = make_customer()
        self.ro = make_repair_order(customer, make_vehicle(customer))

    def test_shared_transition_persists_closed_date_and_repeat_preserves_it(self):
        closed_at = timezone.now() - timedelta(days=2)
        with patch("repair_orders.services.timezone.now", return_value=closed_at):
            transition_repair_order_status(self.ro, "closed")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.closed_at, closed_at)
        count = self.ro.status_history.count()
        transition_repair_order_status(self.ro, "closed")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.closed_at, closed_at)
        self.assertEqual(self.ro.status_history.count(), count)

    def test_two_open_instances_preserve_the_first_closure_date_and_history(self):
        first = RepairOrder.objects.get(pk=self.ro.pk)
        second = RepairOrder.objects.get(pk=self.ro.pk)
        first_time = timezone.now().replace(microsecond=0)
        later_time = first_time + timedelta(hours=1)
        history_clock = RepairOrderStatusHistory._meta.get_field("changed_at")
        with (
            patch("repair_orders.services.timezone.now", return_value=first_time),
            patch.object(history_clock, "get_default", return_value=first_time),
        ):
            transition_repair_order_status(first, "closed", note="First closure")
        original_entry = self.ro.status_history.get(new_status="closed")
        self.assertEqual(original_entry.changed_at, first_time)

        with (
            patch("repair_orders.services.timezone.now", return_value=later_time),
            patch.object(history_clock, "get_default", return_value=later_time),
        ):
            result = transition_repair_order_status(second, "closed", note="Stale duplicate")

        self.ro.refresh_from_db()
        self.assertEqual(self.ro.closed_at, first_time)
        entries = self.ro.status_history.filter(new_status="closed")
        self.assertEqual(entries.count(), 1)
        entry = entries.get()
        self.assertEqual(entry.pk, original_entry.pk)
        self.assertEqual(entry.changed_at, first_time)
        self.assertEqual(entry.note, "First closure")
        self.assertIs(result, second)
        self.assertEqual(second.status, RepairOrder.Status.CLOSED)
        self.assertEqual(second.closed_at, first_time)

    def test_stale_closed_instance_can_close_a_genuinely_reopened_order(self):
        self.ro.internal_notes = "Original inspection notes."
        self.ro.save(update_fields=["internal_notes"])
        self.ro.set_status("closed")
        original_time = self.ro.closed_at
        reopened = RepairOrder.objects.get(pk=self.ro.pk)
        reopened.set_status("in_repair")
        reopened.internal_notes = "New inspection notes saved after reopening."
        reopened.save(update_fields=["internal_notes", "updated_at"])
        later_time = original_time + timedelta(hours=1)

        with patch("repair_orders.services.timezone.now", return_value=later_time):
            result = transition_repair_order_status(self.ro, "closed")

        self.assertIs(result, self.ro)
        self.assertEqual(self.ro.status, RepairOrder.Status.CLOSED)
        self.assertEqual(self.ro.closed_at, later_time)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.internal_notes, reopened.internal_notes)
        self.assertEqual(self.ro.closed_at, later_time)
        self.assertEqual(self.ro.status_history.filter(new_status="closed").count(), 2)
        self.assertEqual(self.ro.status_history.first().previous_status, "in_repair")

    def test_blocked_closure_does_not_set_closed_date(self):
        make_invoice(self.ro)
        count = self.ro.status_history.count()
        with self.assertRaises(RepairOrderStatusTransitionBlocked):
            transition_repair_order_status(self.ro, "closed")
        self.assertIsNone(self.ro.closed_at)
        self.ro.refresh_from_db()
        self.assertIsNone(self.ro.closed_at)
        self.assertEqual(self.ro.status, RepairOrder.Status.INTAKE)
        self.assertEqual(self.ro.status_history.count(), count)

    def test_other_transitions_do_not_create_a_closed_date(self):
        for status in ["delivered", "canceled", "estimating"]:
            with self.subTest(status=status):
                self.ro.set_status(status)
                self.ro.refresh_from_db()
                self.assertIsNone(self.ro.closed_at)

    def test_reclosure_records_the_new_closure_time(self):
        self.ro.set_status("closed")
        first = self.ro.closed_at
        self.ro.set_status("in_repair")
        second = first + timedelta(days=1)
        with patch("repair_orders.services.timezone.now", return_value=second):
            self.ro.set_status("closed")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.closed_at, second)

    def test_failed_history_write_rolls_back_status_and_closed_date(self):
        with patch.object(RepairOrderStatusHistory.objects, "create", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.ro.set_status("closed")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, RepairOrder.Status.INTAKE)
        self.assertIsNone(self.ro.closed_at)


class ClosedDateDisplayTests(TestCase):
    def setUp(self):
        self.manager = make_user()
        self.client.force_login(self.manager)
        customer = make_customer()
        self.ro = make_repair_order(customer, make_vehicle(customer))

    def test_closed_date_survives_detail_reload_and_repeat_post(self):
        self.client.post(status_url(self.ro.pk), {"new_status": "closed"})
        self.ro.refresh_from_db()
        original = self.ro.closed_at
        self.assertIsNotNone(original)
        for _ in range(2):
            response = self.client.get(detail_url(self.ro.pk))
            self.assertEqual(response.context["displayed_closed_at"], original)
            formatted = date_format(timezone.localtime(original), "Y-m-d H:i")
            self.assertContains(response, f"<dt>Closed</dt><dd>{formatted}</dd>", html=True)
            self.client.post(status_url(self.ro.pk), {"new_status": "closed"})
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.closed_at, original)

    def test_legacy_closed_order_displays_latest_closure_without_writing_field(self):
        RepairOrder.objects.filter(pk=self.ro.pk).update(status="closed")
        earlier = timezone.now() - timedelta(days=3)
        latest = timezone.now() - timedelta(days=1)
        for changed_at in [latest, earlier]:
            RepairOrderStatusHistory.objects.create(
                repair_order=self.ro,
                previous_status="delivered",
                new_status="closed",
                changed_at=changed_at,
            )
        response = self.client.get(detail_url(self.ro.pk))
        self.assertEqual(response.context["displayed_closed_at"], latest)
        formatted = date_format(timezone.localtime(latest), "Y-m-d H:i")
        self.assertContains(response, f"<dt>Closed</dt><dd>{formatted}</dd>", html=True)
        self.ro.refresh_from_db()
        self.assertIsNone(self.ro.closed_at)

    def test_existing_closed_date_takes_precedence_over_history(self):
        saved = timezone.now() - timedelta(days=5)
        RepairOrder.objects.filter(pk=self.ro.pk).update(status="closed", closed_at=saved)
        RepairOrderStatusHistory.objects.create(
            repair_order=self.ro, previous_status="delivered", new_status="closed"
        )
        self.assertEqual(
            self.client.get(detail_url(self.ro.pk)).context["displayed_closed_at"], saved
        )

    def test_legacy_closed_order_without_closure_history_stays_blank(self):
        RepairOrder.objects.filter(pk=self.ro.pk).update(status="closed")
        response = self.client.get(detail_url(self.ro.pk))
        self.assertIsNone(response.context["displayed_closed_at"])
        self.assertContains(response, "<dt>Closed</dt><dd>—</dd>", html=True)
        self.ro.refresh_from_db()
        self.assertIsNone(self.ro.closed_at)

    def test_nonclosed_order_does_not_infer_a_closed_date_from_history(self):
        RepairOrderStatusHistory.objects.create(
            repair_order=self.ro, previous_status="delivered", new_status="closed"
        )
        self.assertIsNone(self.client.get(detail_url(self.ro.pk)).context["displayed_closed_at"])
