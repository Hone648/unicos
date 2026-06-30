from django.contrib import admin, messages

from .models import Estimate, EstimateLineItem
from .services import (
    EstimateStatusTransitionBlocked,
    estimate_is_editable,
    transition_estimate_status,
)


class EstimateLineItemInline(admin.TabularInline):
    model = EstimateLineItem
    fields = (
        "item_type",
        "description",
        "quantity",
        "unit_price",
        "line_total_display",
        "sort_order",
    )
    readonly_fields = ("line_total_display",)
    extra = 0
    show_change_link = True

    @admin.display(description="Line total")
    def line_total_display(self, obj):
        if not obj.pk:
            return None
        return obj.line_total

    def has_add_permission(self, request, obj):
        if obj is None:
            return True
        return estimate_is_editable(obj)

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return True
        return estimate_is_editable(obj)

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return True
        return estimate_is_editable(obj)


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = (
        "estimate_number",
        "repair_order",
        "customer_display",
        "kind",
        "parent_estimate",
        "status",
        "approval_source",
        "approval_contact_name",
        "approved_at",
        "insurance_company",
        "claim_number",
        "deductible",
        "estimated_total",
        "updated_at",
    )
    list_filter = ("kind", "status", "approval_source", "insurance_company")
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
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by", "approved_at")
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
            "Approval",
            {
                "fields": (
                    "approval_source",
                    "approval_contact_name",
                    "approval_reference",
                    "approval_note",
                    "approved_at",
                ),
            },
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

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.has_line_items:
            readonly.append("estimated_total")
        return readonly

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user

        if change and form is not None and "status" in form.changed_data:
            # Route the status change through the lifecycle service so
            # allowed-transition rules and approval-capture requirements are
            # enforced uniformly with the shop-facing status action.
            desired_status = obj.status
            obj.status = form.initial["status"]
            obj.updated_by = request.user
            super().save_model(request, obj, form, change)
            approval_data = {
                "approval_source": form.cleaned_data.get("approval_source", ""),
                "approval_contact_name": form.cleaned_data.get("approval_contact_name", ""),
                "approval_reference": form.cleaned_data.get("approval_reference", ""),
                "approval_note": form.cleaned_data.get("approval_note", ""),
            }
            try:
                transition_estimate_status(
                    obj,
                    desired_status,
                    updated_by=request.user,
                    approval_data=approval_data,
                )
            except EstimateStatusTransitionBlocked as exc:
                self.message_user(request, str(exc), level=messages.ERROR)
            return

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
            {
                "fields": (
                    "estimate",
                    "item_type",
                    "description",
                    "quantity",
                    "unit_price",
                    "sort_order",
                )
            },
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

    def has_change_permission(self, request, obj=None):
        if obj is not None and not estimate_is_editable(obj.estimate):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and not estimate_is_editable(obj.estimate):
            return False
        return super().has_delete_permission(request, obj)

    def save_model(self, request, obj, form, change):
        if not estimate_is_editable(obj.estimate):
            self.message_user(
                request,
                f"Estimate {obj.estimate.estimate_number} is not in draft status; "
                "line items cannot be changed.",
                level=messages.ERROR,
            )
            return
        super().save_model(request, obj, form, change)
