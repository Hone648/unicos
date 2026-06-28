from django.contrib import admin

from .models import RepairOrder, RepairOrderStatusHistory


class RepairOrderStatusHistoryInline(admin.TabularInline):
    model = RepairOrderStatusHistory
    fields = ("previous_status", "new_status", "changed_by", "changed_at", "note")
    readonly_fields = ("previous_status", "new_status", "changed_by", "changed_at", "note")
    extra = 0
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
    )
    list_filter = ("status", "assigned_to", "opened_at", "promised_date")
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
    raw_id_fields = ("customer", "vehicle", "assigned_to", "created_by", "updated_by")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    inlines = [RepairOrderStatusHistoryInline]
    fieldsets = (
        (
            "Repair Order",
            {"fields": ("repair_order_number", "status", "assigned_to")},
        ),
        (
            "Customer & Vehicle",
            {"fields": ("customer", "vehicle")},
        ),
        (
            "Dates",
            {"fields": ("opened_at", "promised_date", "closed_at")},
        ),
        (
            "Notes",
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

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        # Pass the current user as status changer so history records correctly.
        obj._status_changed_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RepairOrderStatusHistory)
class RepairOrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("repair_order", "previous_status", "new_status", "changed_by", "changed_at")
    list_filter = ("new_status", "changed_at")
    search_fields = ("repair_order__repair_order_number", "changed_by__username")
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
