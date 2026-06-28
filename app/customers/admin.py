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
        "is_active",
        "created_at",
    )
    list_filter = ("customer_type", "is_active")
    search_fields = (
        "first_name",
        "last_name",
        "business_name",
        "phone_primary",
        "email",
    )
    readonly_fields = ("created_at", "updated_at")
    inlines = [VehicleInline]
    fieldsets = (
        (
            "Customer Type",
            {"fields": ("customer_type", "is_active")},
        ),
        (
            "Individual",
            {"fields": ("first_name", "last_name")},
        ),
        (
            "Business",
            {"fields": ("business_name",)},
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
            "Notes",
            {"fields": ("notes",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
