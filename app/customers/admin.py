from django.contrib import admin
from vehicles.models import Vehicle

from .models import Customer


class VehicleInline(admin.TabularInline):
    model = Vehicle
    fields = ("vin", "year", "make", "model", "license_plate", "is_active")
    readonly_fields = ("vin",)
    extra = 0
    show_change_link = True


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "customer_type",
        "phone_primary",
        "email",
        "city",
        "state",
        "is_active",
        "vehicle_count",
        "repair_order_count",
        "created_at",
    )
    list_filter = ("customer_type", "is_active", "state", "created_at")
    search_fields = (
        "first_name",
        "last_name",
        "business_name",
        "phone_primary",
        "phone_secondary",
        "email",
        "vehicles__vin",
        "vehicles__license_plate",
        "repair_orders__repair_order_number",
    )
    readonly_fields = ("created_at", "updated_at", "vehicle_count", "repair_order_count")
    inlines = [VehicleInline]
    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "customer_type",
                    "is_active",
                    "first_name",
                    "last_name",
                    "business_name",
                )
            },
        ),
        (
            "Contact",
            {"fields": ("phone_primary", "phone_secondary", "email")},
        ),
        (
            "Address",
            {
                "fields": (
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "state",
                    "postal_code",
                )
            },
        ),
        (
            "Operational",
            {
                "fields": ("vehicle_count", "repair_order_count"),
                "description": "Summary counts — read only.",
            },
        ),
        (
            "Notes",
            {"fields": ("notes",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Vehicles")
    def vehicle_count(self, obj):
        return obj.vehicles.count()

    @admin.display(description="Repair orders")
    def repair_order_count(self, obj):
        return obj.repair_orders.count()
