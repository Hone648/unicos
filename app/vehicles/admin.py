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
        "is_active",
    )
    list_filter = ("make", "is_active", "year")
    search_fields = (
        "vin",
        "make",
        "model",
        "license_plate",
        "customer__first_name",
        "customer__last_name",
        "customer__business_name",
    )
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("customer",)
    fieldsets = (
        (
            "Identity",
            {"fields": ("customer", "vin", "is_active")},
        ),
        (
            "Vehicle Details",
            {"fields": ("year", "make", "model", "trim", "color")},
        ),
        (
            "Registration",
            {"fields": ("license_plate", "license_state")},
        ),
        (
            "Other",
            {"fields": ("odometer", "notes")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )
