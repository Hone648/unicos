from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from accounts.authorization import (
    ROLE_ESTIMATOR,
    ROLE_FRONT_DESK,
    ROLE_MANAGER,
    ROLE_OWNER_ADMIN,
    ROLE_READ_ONLY,
    ROLE_TECHNICIAN,
)
from django.contrib import admin
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from estimates.models import Estimate
from repair_orders.admin import RepairOrderAdmin
from repair_orders.models import RepairOrder
from repair_orders.services import (
    RepairOrderTransitionInvalid,
    transition_repair_order_status,
)
from repair_orders.status_continuation import sign_status_continuation
from repair_orders.tests_admin import make_request
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
from repair_orders.transition_policy import ROUTINE_TRANSITIONS

EXPECTED = {
    "intake": ("estimating", "in_repair"),
    "estimating": ("awaiting_approval", "approved"),
    "awaiting_approval": ("approved", "estimating"),
    "approved": ("parts_ordered", "in_repair"),
    "parts_ordered": ("in_repair",),
    "in_repair": ("quality_check",),
    "quality_check": ("ready_for_pickup", "in_repair"),
    "ready_for_pickup": ("delivered", "in_repair"),
    "delivered": ("closed",),
    "closed": (),
    "canceled": (),
}


class TransitionTestCase(TestCase):
    def setUp(self):
        self.manager = make_user()
        self.client.force_login(self.manager)
        customer = make_customer()
        self.ro = make_repair_order(customer, make_vehicle(customer))

    def saved_state(self, status):
        RepairOrder.objects.filter(pk=self.ro.pk).update(status=status)
        self.ro.refresh_from_db()

    def post(self, target, **data):
        return self.client.post(
            status_url(self.ro.pk),
            {
                "new_status": target,
                "expected_status": self.ro.status,
                **data,
            },
            HTTP_HX_REQUEST="true",
        )


class TransitionPolicyTests(TransitionTestCase):
    def test_every_routine_pair_obeys_the_approved_table(self):
        self.assertEqual(ROUTINE_TRANSITIONS, EXPECTED)
        for source, targets in EXPECTED.items():
            for target in RepairOrder.Status.values:
                with self.subTest(source=source, target=target):
                    self.saved_state(source)
                    before = self.ro.status_history.count()
                    if target == source or target in targets:
                        transition_repair_order_status(self.ro, target, changed_by=self.manager)
                        self.ro.refresh_from_db()
                        self.assertEqual(self.ro.status, target)
                        self.assertEqual(
                            self.ro.status_history.count(), before + (target != source)
                        )
                    else:
                        with self.assertRaises(RepairOrderTransitionInvalid):
                            transition_repair_order_status(self.ro, target, changed_by=self.manager)
                        self.ro.refresh_from_db()
                        self.assertEqual(self.ro.status, source)
                        self.assertEqual(self.ro.status_history.count(), before)

    def test_detail_options_match_saved_state_and_terminal_empty_state(self):
        for source, targets in EXPECTED.items():
            with self.subTest(source=source):
                self.saved_state(source)
                response = self.client.get(detail_url(self.ro.pk))
                self.assertEqual([x[0] for x in response.context["status_choices"]], list(targets))
                self.assertContains(
                    response,
                    f"Current status: <strong>{self.ro.get_status_display()}</strong>",
                    html=True,
                )
                if not targets:
                    self.assertContains(response, "No routine status transitions are available.")
                    self.assertNotContains(response, 'id="new_status"')

    def test_routine_forms_require_a_deliberate_choice_and_reset_after_htmx(self):
        for source, targets in EXPECTED.items():
            if not targets:
                continue
            with self.subTest(source=source):
                self.saved_state(source)
                response = self.client.get(detail_url(self.ro.pk))
                self.assertEqual(response.context["selected_status"], "")
                self.assertContains(response, '<select id="new_status" name="new_status" required>')
                self.assertContains(
                    response, '<option value="" selected>Choose next status…</option>', html=True
                )
        self.saved_state("parts_ordered")
        updated = self.post("in_repair")
        self.assertEqual(updated.context["selected_status"], "")
        self.assertContains(
            updated, '<option value="" selected>Choose next status…</option>', html=True
        )

    def test_empty_delivered_to_closed_submission_does_not_write(self):
        self.saved_state("delivered")
        before = list(self.ro.status_history.values())
        date = self.ro.closed_at
        for target in ["", "   "]:
            with self.subTest(target=target):
                response = self.post(target)
                self.assertContains(
                    response, "Choose a next status before selecting Update Status."
                )
                self.assertEqual(response.context["selected_status"], "")
                self.ro.refresh_from_db()
                self.assertEqual(self.ro.status, "delivered")
                self.assertEqual(self.ro.closed_at, date)
                self.assertEqual(list(self.ro.status_history.values()), before)

    def test_stale_submission_refreshes_choices_even_when_target_is_still_legal(self):
        self.saved_state("approved")
        response = self.post("in_repair", expected_status="intake")
        self.assertContains(response, "Status changed to Approved")
        self.assertEqual(
            response.context["status_choices"],
            [("parts_ordered", "Parts ordered"), ("in_repair", "In repair")],
        )
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "approved")

    def test_missing_expected_status_and_prohibited_jump_do_not_write(self):
        missing = self.client.post(
            status_url(self.ro.pk), {"new_status": "in_repair"}, HTTP_HX_REQUEST="true"
        )
        self.assertContains(missing, "Reload this page")
        jump = self.post("ready_for_pickup")
        self.assertContains(jump, "cannot change directly")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "intake")
        self.assertEqual(self.ro.status_history.count(), 1)

    def test_locked_transition_preserves_newer_edits(self):
        self.saved_state("quality_check")
        stale = RepairOrder.objects.get(pk=self.ro.pk)
        RepairOrder.objects.filter(pk=self.ro.pk).update(internal_notes="Newer inspection notes")
        result = transition_repair_order_status(
            stale, "in_repair", changed_by=self.manager, expected_status="quality_check"
        )
        self.assertIs(result, stale)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.internal_notes, "Newer inspection notes")
        self.assertEqual(self.ro.status_history.first().previous_status, "quality_check")

    def test_routine_permission_roles(self):
        for role, permitted in [
            (ROLE_OWNER_ADMIN, True),
            (ROLE_MANAGER, True),
            (ROLE_ESTIMATOR, True),
            (ROLE_FRONT_DESK, False),
            (ROLE_TECHNICIAN, False),
            (ROLE_READ_ONLY, False),
        ]:
            with self.subTest(role=role):
                self.saved_state("parts_ordered")
                user = make_user(username=f"routine-{role}", role_name=role)
                self.ro.assigned_to = user
                self.ro.save(update_fields=["assigned_to"])
                self.client.force_login(user)
                response = self.post("in_repair")
                self.assertEqual(response.status_code, 200 if permitted else 403)
                self.ro.refresh_from_db()
                self.assertEqual(self.ro.status, "in_repair" if permitted else "parts_ordered")

    def test_duplicate_close_preserves_date_and_history_under_lock(self):
        self.saved_state("delivered")
        first = RepairOrder.objects.get(pk=self.ro.pk)
        second = RepairOrder.objects.get(pk=self.ro.pk)
        at = timezone.now()
        with patch("repair_orders.services.timezone.now", return_value=at):
            transition_repair_order_status(first, "closed", changed_by=self.manager)
        original = first.status_history.first()
        with patch("repair_orders.services.timezone.now", return_value=at + timedelta(hours=1)):
            result = transition_repair_order_status(
                second, "closed", changed_by=self.manager, expected_status="delivered"
            )
        self.assertIs(result, second)
        self.assertEqual(second.closed_at, at)
        self.assertEqual(second.status_history.filter(new_status="closed").count(), 1)
        self.assertEqual(second.status_history.first().pk, original.pk)


class ExceptionTransitionTests(TransitionTestCase):
    # Inherit fixture helpers, not the routine policy tests.
    def test_exception_roles_and_required_reasons(self):
        for role, permitted in [
            (ROLE_OWNER_ADMIN, True),
            (ROLE_MANAGER, True),
            (ROLE_ESTIMATOR, False),
            (ROLE_FRONT_DESK, False),
            (ROLE_TECHNICIAN, False),
            (ROLE_READ_ONLY, False),
        ]:
            with self.subTest(role=role):
                self.saved_state("intake")
                user = make_user(username=f"exception-{role}", role_name=role)
                self.client.force_login(user)
                self.post("", transition_action="cancel", reason="  ")
                self.ro.refresh_from_db()
                self.assertEqual(self.ro.status, "intake")
                self.post("", transition_action="cancel", reason="Customer declined repairs")
                self.ro.refresh_from_db()
                self.assertEqual(self.ro.status, "canceled" if permitted else "intake")
                if permitted:
                    entry = self.ro.status_history.first()
                    self.assertEqual(entry.changed_by, user)
                    self.assertEqual(entry.note, "Customer declined repairs")

    def test_cancel_only_before_delivery_and_reopen_exact_targets(self):
        for status in EXPECTED:
            with self.subTest(source=status):
                self.saved_state(status)
                if status in {"delivered", "closed", "canceled"}:
                    with self.assertRaises(RepairOrderTransitionInvalid):
                        transition_repair_order_status(
                            self.ro,
                            "canceled",
                            changed_by=self.manager,
                            action="cancel",
                            reason="Requested",
                        )
                else:
                    transition_repair_order_status(
                        self.ro,
                        "canceled",
                        changed_by=self.manager,
                        action="cancel",
                        reason="Requested",
                    )
                    self.assertEqual(self.ro.status, "canceled")
        for source, target in [("closed", "in_repair"), ("canceled", "intake")]:
            self.saved_state(source)
            with self.assertRaises(RepairOrderTransitionInvalid):
                transition_repair_order_status(
                    self.ro, target, changed_by=self.manager, action="reopen", reason=""
                )
            transition_repair_order_status(
                self.ro,
                target,
                changed_by=self.manager,
                action="reopen",
                reason="Additional work authorized",
            )
            self.assertEqual(self.ro.status, target)
            self.assertEqual(self.ro.status_history.first().previous_status, source)

    def test_exception_records_and_financial_documents_stay_intact(self):
        estimate = Estimate.objects.create(repair_order=self.ro, estimate_number="EST-KEPT")
        invoice = make_invoice(self.ro)
        payment = make_payment(invoice, Decimal("440.00"))
        transition_repair_order_status(
            self.ro,
            "canceled",
            changed_by=self.manager,
            action="cancel",
            reason="Customer canceled",
        )
        transition_repair_order_status(
            self.ro, "intake", changed_by=self.manager, action="reopen", reason="Customer returned"
        )
        self.assertTrue(self.ro.estimates.filter(pk=estimate.pk).exists())
        self.assertTrue(invoice.payments.filter(pk=payment.pk).exists())
        invoice.refresh_from_db()
        self.assertNotEqual(invoice.status, "void")
        self.assertEqual(self.ro.status_history.count(), 3)


class TransitionPaymentTests(TransitionTestCase):
    def test_partial_full_payment_and_explicit_delivered_retry(self):
        self.saved_state("ready_for_pickup")
        invoice = make_invoice(self.ro, subtotal=Decimal("100.00"), tax_amount=Decimal("0.00"))
        response = self.post("delivered")
        self.assertContains(response, "has a balance due of $100.00.")
        payment_url = reverse("billing:payment_create", kwargs={"invoice_pk": invoice.pk})
        token = parse_qs(urlsplit(response.context["status_payment_url"]).query)[
            "status_continuation"
        ][0]
        for amount, remaining in [("40.00", True), ("60.00", False)]:
            response = self.client.post(
                payment_url,
                {
                    "status_continuation": token,
                    "payment_date": "2026-11-22",
                    "amount": amount,
                    "method": "cash",
                },
                follow=True,
            )
            self.ro.refresh_from_db()
            self.assertEqual(self.ro.status, "ready_for_pickup")
            self.assertIsNone(self.ro.closed_at)
            self.assertEqual(response.context["selected_status"], "delivered")
            if remaining:
                self.assertContains(response, "has a remaining balance of $60.00.")
            else:
                self.assertContains(
                    response, "Select Update Status to mark this repair order as delivered."
                )
            token = parse_qs(urlsplit(response.redirect_chain[-1][0]).query)["status_continuation"][
                0
            ]
        self.post("delivered")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "delivered")
        self.assertIsNone(self.ro.closed_at)
        self.post("closed")
        self.ro.refresh_from_db()
        self.assertIsNotNone(self.ro.closed_at)

    def test_status_change_after_initial_continuation_check_does_not_record_payment(self):
        from repair_orders.status_continuation import validated_continuation

        self.saved_state("ready_for_pickup")
        invoice = make_invoice(self.ro, subtotal=Decimal("100.00"), tax_amount=Decimal("0.00"))
        existing = make_payment(invoice, Decimal("20.00"))
        invoice.sync_payment_status()
        invoice.refresh_from_db()
        original_status = invoice.status
        token = sign_status_continuation(invoice, "delivered")

        def initial_check_then_rework(*args):
            continuation = validated_continuation(*args)
            self.assertIsNotNone(continuation)
            current = RepairOrder.objects.get(pk=self.ro.pk)
            transition_repair_order_status(current, "in_repair", changed_by=self.manager)
            return continuation

        with patch(
            "billing.views.validated_continuation", side_effect=initial_check_then_rework
        ) as check:
            response = self.client.post(
                reverse("billing:payment_create", kwargs={"invoice_pk": invoice.pk}),
                {
                    "status_continuation": token,
                    "payment_date": "2026-11-22",
                    "amount": "40.00",
                    "method": "cash",
                },
                follow=True,
            )
        check.assert_called_once()
        invoice.refresh_from_db()
        self.assertEqual(list(invoice.payments.values_list("pk", flat=True)), [existing.pk])
        self.assertEqual(invoice.balance_due, Decimal("80.00"))
        self.assertEqual(invoice.status, original_status)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "in_repair")
        self.assertContains(response, "Payment was not recorded.")
        self.assertEqual(response.context["status_choices"], [("quality_check", "Quality check")])
        self.assertEqual(response.context["selected_status"], "")
        self.assertNotIn("status_continuation", urlsplit(response.redirect_chain[-1][0]).query)

    def test_invoice_reassignment_after_form_validation_does_not_record_payment(self):
        from billing.models import Invoice
        from billing.services import record_payment
        from repair_orders.status_continuation import validated_continuation

        self.saved_state("ready_for_pickup")
        invoice = make_invoice(self.ro, subtotal=Decimal("100.00"), tax_amount=Decimal("0.00"))
        existing = make_payment(invoice, Decimal("20.00"))
        invoice.sync_payment_status()
        invoice.refresh_from_db()
        other = make_repair_order(self.ro.customer, self.ro.vehicle, number="RO-REASSIGNED")
        expected_invoice = Invoice.objects.filter(pk=invoice.pk).values().get()
        expected_invoice["repair_order_id"] = other.pk
        token = sign_status_continuation(invoice, "delivered")

        def reassign_then_record(stale_invoice, data, **kwargs):
            initial_check.assert_called_once()
            self.assertEqual(data["amount"], Decimal("40.00"))
            self.assertEqual(stale_invoice.repair_order_id, self.ro.pk)
            Invoice.objects.filter(pk=invoice.pk).update(repair_order=other)
            return record_payment(stale_invoice, data, **kwargs)

        with (
            patch(
                "billing.views.validated_continuation", wraps=validated_continuation
            ) as initial_check,
            patch("billing.views.record_payment", side_effect=reassign_then_record) as write,
        ):
            response = self.client.post(
                reverse("billing:payment_create", kwargs={"invoice_pk": invoice.pk}),
                {
                    "status_continuation": token,
                    "payment_date": "2026-11-22",
                    "amount": "40.00",
                    "method": "cash",
                },
                follow=True,
            )
        write.assert_called_once()
        invoice.refresh_from_db()
        self.assertEqual(invoice.repair_order_id, other.pk)
        self.assertEqual(list(invoice.payments.values_list("pk", flat=True)), [existing.pk])
        self.assertEqual(invoice.balance_due, Decimal("80.00"))
        self.assertEqual(Invoice.objects.filter(pk=invoice.pk).values().get(), expected_invoice)
        self.assertEqual(response.redirect_chain, [(detail_url(self.ro.pk), 302)])
        self.assertContains(response, "Payment was not recorded.")
        self.assertEqual(response.context["ro"].pk, self.ro.pk)
        self.assertEqual(response.context["ro"].status, "ready_for_pickup")
        self.assertEqual(response.context["selected_status"], "")
        self.assertEqual(
            [value for value, _ in response.context["status_choices"]], ["delivered", "in_repair"]
        )

    def test_cancellation_payment_retry_requires_reason_again(self):
        invoice = make_invoice(self.ro)
        response = self.post("", transition_action="cancel", reason="Customer canceled")
        token = parse_qs(urlsplit(response.context["status_payment_url"]).query)[
            "status_continuation"
        ][0]
        paid = self.client.post(
            reverse("billing:payment_create", kwargs={"invoice_pk": invoice.pk}),
            {
                "status_continuation": token,
                "payment_date": "2026-11-22",
                "amount": "440.00",
                "method": "cash",
            },
            follow=True,
        )
        self.assertContains(paid, "Enter a cancellation reason and select Cancel Repair Order.")
        self.assertContains(
            paid, '<option value="" selected>Choose next status…</option>', html=True
        )
        self.assertContains(paid, '<details class="mt-3" open>', html=False)
        self.assertEqual(paid.context["pending_action"], "cancel")
        self.post("", transition_action="cancel", reason=" ")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "intake")
        self.post("", transition_action="cancel", reason="Customer canceled")
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "canceled")
        self.assertEqual(self.ro.status_history.first().note, "Customer canceled")

    def test_stale_or_revoked_continuation_returns_current_choices_without_payment(self):
        self.saved_state("ready_for_pickup")
        invoice = make_invoice(self.ro)
        token = sign_status_continuation(invoice, "delivered")
        self.saved_state("in_repair")
        response = self.client.get(detail_url(self.ro.pk), {"status_continuation": token})
        self.assertContains(response, "pending action is no longer available")
        self.assertEqual(response.context["status_choices"], [("quality_check", "Quality check")])
        url = reverse("billing:payment_create", kwargs={"invoice_pk": invoice.pk})
        stale = self.client.post(
            url,
            {
                "status_continuation": token,
                "payment_date": "2026-11-22",
                "amount": "40.00",
                "method": "cash",
            },
        )
        self.assertRedirects(stale, detail_url(self.ro.pk))
        self.assertFalse(invoice.payments.exists())
        self.saved_state("ready_for_pickup")
        self.manager.groups.clear()
        response = self.client.get(url, {"status_continuation": token})
        self.assertEqual(response.status_code, 403)


class TransitionAdminTests(TransitionTestCase):
    def setUp(self):
        super().setUp()
        self.admin = RepairOrderAdmin(RepairOrder, admin.site)
        self.request = make_request(self.manager)

    def test_admin_form_choices_and_new_orders_start_intake(self):
        self.saved_state("parts_ordered")
        form = self.admin.get_form(self.request, self.ro)(instance=self.ro)
        self.assertEqual(
            [x[0] for x in form.fields["status"].choices], ["parts_ordered", "in_repair"]
        )
        fresh = RepairOrder(
            repair_order_number="RO-ADMIN-NEW",
            customer=self.ro.customer,
            vehicle=self.ro.vehicle,
            status="closed",
        )
        self.admin.save_model(self.request, fresh, None, change=False)
        self.assertEqual(fresh.status, "intake")
        self.assertEqual(fresh.status_history.get().new_status, "intake")

    def test_bulk_routine_actions_cannot_jump(self):
        self.admin.mark_closed(self.request, RepairOrder.objects.filter(pk=self.ro.pk))
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "intake")
        self.saved_state("delivered")
        self.admin.mark_closed(self.request, RepairOrder.objects.filter(pk=self.ro.pk))
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "closed")

    def test_bulk_exceptions_require_role_and_reason(self):
        self.admin.mark_canceled(self.request, RepairOrder.objects.filter(pk=self.ro.pk))
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "intake")
        request = make_request(self.manager)
        request.POST = request.POST.copy()
        request.POST["transition_reason"] = "Customer requested cancellation"
        self.admin.mark_canceled(request, RepairOrder.objects.filter(pk=self.ro.pk))
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "canceled")
        self.admin.reopen_repair_orders(request, RepairOrder.objects.filter(pk=self.ro.pk))
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "intake")
        self.assertEqual(self.ro.status_history.first().note, "Customer requested cancellation")
        estimator = make_user(username="admin-estimator", role_name=ROLE_ESTIMATOR)
        request.user = estimator
        self.admin.mark_canceled(request, RepairOrder.objects.filter(pk=self.ro.pk))
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "intake")

    def test_stale_admin_form_does_not_restore_status_or_notes(self):
        stale = RepairOrder.objects.get(pk=self.ro.pk)
        RepairOrder.objects.filter(pk=self.ro.pk).update(
            status="approved", internal_notes="Newer notes"
        )
        stale.status = "in_repair"
        form = SimpleNamespace(changed_data=["status"], cleaned_data={"expected_status": "intake"})
        self.admin.save_model(self.request, stale, form, change=True)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "approved")
        self.assertEqual(self.ro.internal_notes, "Newer notes")

    def test_admin_http_bulk_exception_and_forged_form_status(self):
        superuser = make_user(username="transition-admin", is_superuser=True, is_staff=True)
        self.client.force_login(superuser)
        change_url = reverse("admin:repair_orders_repairorder_change", args=[self.ro.pk])
        page = self.client.get(change_url)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(
            [x[0] for x in page.context["adminform"].form.fields["status"].choices],
            ["intake", "estimating", "in_repair"],
        )
        invalid = self.client.post(
            change_url,
            {
                "status": "closed",
                "expected_status": "intake",
                "repair_order_number": self.ro.repair_order_number,
                "customer": self.ro.customer_id,
                "vehicle": self.ro.vehicle_id,
            },
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn("status", invalid.context["adminform"].form.errors)
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "intake")
        changelist = reverse("admin:repair_orders_repairorder_changelist")
        blocked = self.client.post(
            changelist,
            {"action": "mark_canceled", "_selected_action": [self.ro.pk], "index": "0"},
            follow=True,
        )
        self.assertContains(blocked, "nonblank reason")
        self.client.post(
            changelist,
            {
                "action": "mark_canceled",
                "_selected_action": [self.ro.pk],
                "index": "0",
                "transition_reason": "Customer canceled",
            },
        )
        self.ro.refresh_from_db()
        self.assertEqual(self.ro.status, "canceled")
        self.assertEqual(self.ro.status_history.first().changed_by, superuser)
        self.assertEqual(self.ro.status_history.first().note, "Customer canceled")

    def test_admin_without_status_role_sees_only_current_status(self):
        reader = make_user(username="admin-reader", role_name=ROLE_READ_ONLY, is_staff=True)
        request = make_request(reader)
        form = self.admin.get_form(request, self.ro)(instance=self.ro)
        self.assertEqual(list(form.fields["status"].choices), [("intake", "Intake")])
        self.assertNotIn("mark_estimating", self.admin.get_actions(request))
        self.assertNotIn("mark_canceled", self.admin.get_actions(request))
