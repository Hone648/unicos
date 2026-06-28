from django.contrib import admin

from .models import Vehicle


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = (
        "vin",
        "customer",
        "year",
        "make",
        "model",
        "license_plate",
        "license_state",
        "is_active",
        "repair_order_count",
        "created_at",
    )
    list_filter = ("make", "year", "license_state", "is_active", "created_at")
    search_fields = (
        "vin",
        "make",
        "model",
        "license_plate",
        "customer__first_name",
        "customer__last_name",
        "customer__business_name",
        "repair_orders__repair_order_number",
    )
    list_select_related = ("customer",)
    raw_id_fields = ("customer",)
    readonly_fields = ("created_at", "updated_at", "repair_order_count")
    fieldsets = (
        (
            "Customer",
            {"fields": ("customer",)},
        ),
        (
            "Vehicle Identity",
            {"fields": ("vin", "year", "make", "model", "trim", "color", "is_active")},
        ),
        (
            "Registration",
            {"fields": ("license_plate", "license_state")},
        ),
        (
            "Condition / Notes",
            {"fields": ("odometer", "notes", "repair_order_count")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Repair orders")
    def repair_order_count(self, obj):
        return obj.repair_orders.count()
