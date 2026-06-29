from django.contrib import admin

from .models import Estimate


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = (
        "estimate_number",
        "repair_order",
        "customer_display",
        "status",
        "insurance_company",
        "claim_number",
        "deductible",
        "estimated_total",
        "updated_at",
    )
    list_filter = ("status", "insurance_company")
    search_fields = (
        "estimate_number",
        "repair_order__repair_order_number",
        "insurance_company",
        "claim_number",
        "repair_order__customer__first_name",
        "repair_order__customer__last_name",
        "repair_order__customer__business_name",
    )
    list_select_related = (
        "repair_order",
        "repair_order__customer",
        "repair_order__vehicle",
        "created_by",
        "updated_by",
    )
    raw_id_fields = ("repair_order", "created_by", "updated_by")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    fieldsets = (
        (
            "Estimate",
            {"fields": ("repair_order", "estimate_number", "status")},
        ),
        (
            "Insurance / Claim",
            {"fields": ("insurance_company", "claim_number", "deductible")},
        ),
        (
            "Amounts",
            {"fields": ("estimated_total",)},
        ),
        (
            "Notes",
            {"fields": ("notes",)},
        ),
        (
            "Tracking",
            {
                "fields": ("created_by", "updated_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Customer")
    def customer_display(self, obj):
        return obj.repair_order.customer

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
