from django.contrib import admin

from .models import Estimate, EstimateLineItem


class EstimateLineItemInline(admin.TabularInline):
    model = EstimateLineItem
    fields = ("item_type", "description", "quantity", "unit_price", "line_total_display", "sort_order")
    readonly_fields = ("line_total_display",)
    extra = 0
    show_change_link = True

    @admin.display(description="Line total")
    def line_total_display(self, obj):
        if not obj.pk:
            return None
        return obj.line_total


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = (
        "estimate_number",
        "repair_order",
        "customer_display",
        "kind",
        "parent_estimate",
        "status",
        "insurance_company",
        "claim_number",
        "deductible",
        "estimated_total",
        "updated_at",
    )
    list_filter = ("kind", "status", "insurance_company")
    search_fields = (
        "estimate_number",
        "parent_estimate__estimate_number",
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
        "parent_estimate",
        "created_by",
        "updated_by",
    )
    raw_id_fields = ("repair_order", "parent_estimate", "created_by", "updated_by")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    inlines = [EstimateLineItemInline]
    fieldsets = (
        (
            "Estimate",
            {"fields": ("repair_order", "estimate_number", "status", "kind", "parent_estimate")},
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


@admin.register(EstimateLineItem)
class EstimateLineItemAdmin(admin.ModelAdmin):
    list_display = (
        "estimate",
        "item_type",
        "description",
        "quantity",
        "unit_price",
        "line_total_display",
        "updated_at",
    )
    list_filter = ("item_type",)
    search_fields = (
        "estimate__estimate_number",
        "estimate__repair_order__repair_order_number",
        "description",
    )
    list_select_related = ("estimate", "estimate__repair_order")
    raw_id_fields = ("estimate",)
    readonly_fields = ("created_at", "updated_at", "line_total_display")
    fieldsets = (
        (
            "Line item",
            {"fields": ("estimate", "item_type", "description", "quantity", "unit_price", "sort_order")},
        ),
        (
            "Calculated",
            {"fields": ("line_total_display",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Line total")
    def line_total_display(self, obj):
        return obj.line_total
