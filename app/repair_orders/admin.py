from accounts.authorization import PERM_REPAIR_ORDERS_CHANGE_STATUS, user_has_app_permission
from accounts.policies import can_change_repair_order_status, is_owner_admin_or_manager
from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.db import transaction

from .models import RepairOrder, RepairOrderStatusHistory
from .services import (
    RepairOrderLifecycleError,
    RepairOrderTransitionInvalid,
    transition_repair_order_status,
)
from .transition_policy import REOPEN_TARGETS, routine_choices, transition_error

_ACTION_NOTE = "Status changed from Django admin action."


class RepairOrderActionForm(ActionForm):
    transition_reason = forms.CharField(
        required=False, max_length=500, label="Cancel/reopen reason"
    )


class RepairOrderAdminForm(forms.ModelForm):
    expected_status = forms.CharField(widget=forms.HiddenInput)
    transition_actor = None

    class Meta:
        model = RepairOrder
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saved_status = self.instance.status if self.instance.pk else RepairOrder.Status.INTAKE
        self.fields["expected_status"].initial = self.saved_status
        self.fields["status"].choices = [
            (self.saved_status, dict(RepairOrder.Status.choices)[self.saved_status])
        ] + (
            routine_choices(self.saved_status)
            if can_change_repair_order_status(self.transition_actor, self.instance)
            else []
        )
        if not self.instance.pk:
            self.fields["status"].initial = RepairOrder.Status.INTAKE
            self.fields["status"].disabled = True

    def clean(self):
        data = super().clean()
        if self.instance.pk and data.get("expected_status") != self.saved_status:
            raise forms.ValidationError(
                "Status changed since this page was loaded. Reload to review the current choices."
            )
        target = data.get("status")
        if self.instance.pk and target and target != self.saved_status:
            error = transition_error(self.instance, target, actor=self.transition_actor)
            if error:
                raise forms.ValidationError(error)
        return data


class RepairOrderStatusHistoryInline(admin.TabularInline):
    model = RepairOrderStatusHistory
    fields = ("previous_status", "new_status", "changed_by", "changed_at", "note")
    readonly_fields = ("previous_status", "new_status", "changed_by", "changed_at", "note")
    extra = 0
    max_num = 0
    can_delete = False
    ordering = ("-changed_at", "-id")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(RepairOrder)
class RepairOrderAdmin(admin.ModelAdmin):
    form = RepairOrderAdminForm
    action_form = RepairOrderActionForm
    list_display = (
        "repair_order_number",
        "customer",
        "vehicle",
        "status",
        "assigned_to",
        "opened_at",
        "promised_date",
        "closed_at",
        "is_closed_display",
    )
    list_filter = ("status", "assigned_to", "opened_at", "promised_date", "closed_at")
    search_fields = (
        "repair_order_number",
        "customer__first_name",
        "customer__last_name",
        "customer__business_name",
        "vehicle__vin",
        "vehicle__make",
        "vehicle__model",
        "vehicle__license_plate",
    )
    list_select_related = ("customer", "vehicle", "assigned_to", "created_by", "updated_by")
    date_hierarchy = "opened_at"
    raw_id_fields = ("customer", "vehicle", "assigned_to", "created_by", "updated_by")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by", "is_closed_display")
    inlines = [RepairOrderStatusHistoryInline]
    actions = [
        "mark_estimating",
        "mark_awaiting_approval",
        "mark_approved",
        "mark_parts_ordered",
        "mark_in_repair",
        "mark_quality_check",
        "mark_ready_for_pickup",
        "mark_delivered",
        "mark_closed",
        "mark_canceled",
        "reopen_repair_orders",
    ]
    fieldsets = (
        (
            "Repair Order",
            {"fields": ("repair_order_number", "status", "expected_status", "is_closed_display")},
        ),
        (
            "Customer & Vehicle",
            {"fields": ("customer", "vehicle")},
        ),
        (
            "Assignment",
            {"fields": ("assigned_to",)},
        ),
        (
            "Dates",
            {"fields": ("opened_at", "promised_date", "closed_at")},
        ),
        (
            "Problem / Notes",
            {"fields": ("reported_problem", "internal_notes")},
        ),
        (
            "Tracking",
            {
                "fields": ("created_by", "updated_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(boolean=True, description="Closed?")
    def is_closed_display(self, obj):
        return obj.is_closed

    def get_form(self, request, obj=None, **kwargs):
        base = super().get_form(request, obj, **kwargs)

        class BoundForm(base):
            transition_actor = request.user

        return BoundForm

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not user_has_app_permission(request.user, PERM_REPAIR_ORDERS_CHANGE_STATUS):
            for name in list(actions):
                if name.startswith("mark_"):
                    actions.pop(name)
        if not is_owner_admin_or_manager(request.user):
            actions.pop("mark_canceled", None)
            actions.pop("reopen_repair_orders", None)
        return actions

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if not change:
            obj.status = RepairOrder.Status.INTAKE
            obj.created_by = obj.created_by or request.user
            obj.updated_by = request.user
            super().save_model(request, obj, form, change)
            return

        current = RepairOrder.objects.select_for_update().get(pk=obj.pk)
        target = obj.status
        expected = getattr(form, "cleaned_data", {}).get(
            "expected_status", getattr(form, "initial", {}).get("status", obj.status)
        )
        try:
            if expected != current.status:
                raise RepairOrderTransitionInvalid(
                    "Status changed since this page was loaded. Reload to review current choices."
                )
            if target != current.status:
                error = transition_error(current, target, actor=request.user)
                if error:
                    raise RepairOrderTransitionInvalid(error)
            changed_fields = getattr(form, "changed_data", None)
            if changed_fields is None:
                changed_fields = [
                    field.name for field in obj._meta.concrete_fields if field.editable
                ]
            for name in changed_fields:
                if name not in {"status", "expected_status", "id"}:
                    setattr(current, name, getattr(obj, name))
            current.updated_by = request.user
            current.save()
            if target != current.status:
                transition_repair_order_status(
                    current,
                    target,
                    changed_by=request.user,
                    note="Status changed from Django admin.",
                    expected_status=expected,
                )
        except RepairOrderLifecycleError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
        obj.refresh_from_db()

    def _apply_status_action(self, request, queryset, target_status=None, *, action="routine"):
        updated = 0
        blocked = 0
        reason = request.POST.get("transition_reason", "").strip()
        for ro in queryset:
            target = REOPEN_TARGETS.get(ro.status, "") if action == "reopen" else target_status
            if action == "routine" and ro.status == target:
                continue
            try:
                transition_repair_order_status(
                    ro,
                    target,
                    changed_by=request.user,
                    note=_ACTION_NOTE,
                    action=action,
                    reason=reason,
                    expected_status=ro.status,
                )
                updated += 1
            except RepairOrderLifecycleError as exc:
                blocked += 1
                self.message_user(request, str(exc), level=messages.ERROR)
        if updated:
            self.message_user(request, f"{updated} repair order(s) updated.")
        if blocked:
            self.message_user(
                request,
                f"{blocked} repair order(s) could not be updated due to lifecycle rules.",
                level=messages.WARNING,
            )

    # ------------------------------------------------------------------
    # Status-change actions
    # ------------------------------------------------------------------

    @admin.action(description="Mark as: Estimating")
    def mark_estimating(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.ESTIMATING)

    @admin.action(description="Mark as: Awaiting approval")
    def mark_awaiting_approval(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.AWAITING_APPROVAL)

    @admin.action(description="Mark as: Approved")
    def mark_approved(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.APPROVED)

    @admin.action(description="Mark as: Parts ordered")
    def mark_parts_ordered(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.PARTS_ORDERED)

    @admin.action(description="Mark as: In repair")
    def mark_in_repair(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.IN_REPAIR)

    @admin.action(description="Mark as: Quality check")
    def mark_quality_check(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.QUALITY_CHECK)

    @admin.action(description="Mark as: Ready for pickup")
    def mark_ready_for_pickup(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.READY_FOR_PICKUP)

    @admin.action(description="Mark as: Delivered")
    def mark_delivered(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.DELIVERED)

    @admin.action(description="Mark as: Closed")
    def mark_closed(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.CLOSED)

    @admin.action(description="Cancel Repair Orders (reason required)")
    def mark_canceled(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.CANCELED, action="cancel")

    @admin.action(description="Reopen Repair Orders (reason required)")
    def reopen_repair_orders(self, request, queryset):
        self._apply_status_action(request, queryset, action="reopen")


@admin.register(RepairOrderStatusHistory)
class RepairOrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("repair_order", "previous_status", "new_status", "changed_by", "changed_at")
    list_filter = ("new_status", "changed_at", "changed_by")
    search_fields = (
        "repair_order__repair_order_number",
        "changed_by__username",
        "changed_by__email",
    )
    list_select_related = ("repair_order", "changed_by")
    date_hierarchy = "changed_at"
    readonly_fields = (
        "repair_order",
        "previous_status",
        "new_status",
        "changed_by",
        "changed_at",
        "note",
    )
    ordering = ("-changed_at", "-id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
