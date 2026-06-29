from django.contrib import admin, messages

from .models import RepairOrder, RepairOrderStatusHistory

_ACTION_NOTE = "Status changed from Django admin action."


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
        "mark_in_repair",
        "mark_quality_check",
        "mark_ready_for_pickup",
        "mark_closed",
        "mark_canceled",
    ]
    fieldsets = (
        (
            "Repair Order",
            {"fields": ("repair_order_number", "status", "is_closed_display")},
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

    def save_model(self, request, obj, form, change):
        from .services import RepairOrderStatusTransitionBlocked, transition_repair_order_status

        if not change and not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user

        if change and form is not None and "status" in form.changed_data:
            # Route the status change through the lifecycle service so rules
            # are enforced uniformly.  Save other field changes first with
            # the original status, then let the service apply the transition.
            desired_status = obj.status
            obj.status = form.initial["status"]
            super().save_model(request, obj, form, change)
            try:
                transition_repair_order_status(
                    obj, desired_status,
                    changed_by=request.user,
                    note="Status changed from Django admin.",
                )
            except RepairOrderStatusTransitionBlocked as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
        else:
            # Pass the current user as status changer so history records correctly.
            obj._status_changed_by = request.user
            super().save_model(request, obj, form, change)

    # ------------------------------------------------------------------
    # Shared action helper
    # ------------------------------------------------------------------

    def _apply_status_action(self, request, queryset, target_status):
        from .services import RepairOrderStatusTransitionBlocked

        updated = 0
        blocked = 0
        for ro in queryset:
            if ro.status == target_status:
                continue
            try:
                ro.set_status(target_status, changed_by=request.user, note=_ACTION_NOTE)
                updated += 1
            except RepairOrderStatusTransitionBlocked as exc:
                blocked += 1
                self.message_user(request, str(exc), level=messages.ERROR)
        label = RepairOrder.Status(target_status).label
        if updated:
            self.message_user(request, f"{updated} repair order(s) set to '{label}'.")
        if blocked:
            self.message_user(
                request,
                f"{blocked} repair order(s) could not be set to '{label}' due to lifecycle rules.",
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

    @admin.action(description="Mark as: In repair")
    def mark_in_repair(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.IN_REPAIR)

    @admin.action(description="Mark as: Quality check")
    def mark_quality_check(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.QUALITY_CHECK)

    @admin.action(description="Mark as: Ready for pickup")
    def mark_ready_for_pickup(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.READY_FOR_PICKUP)

    @admin.action(description="Mark as: Closed")
    def mark_closed(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.CLOSED)

    @admin.action(description="Mark as: Canceled")
    def mark_canceled(self, request, queryset):
        self._apply_status_action(request, queryset, RepairOrder.Status.CANCELED)


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
