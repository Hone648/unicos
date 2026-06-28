from django.contrib import admin

from .models import Invoice, InvoiceLineItem, Payment


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    fields = ("item_type", "description", "quantity", "unit_price", "line_total_display")
    readonly_fields = ("line_total_display",)
    extra = 0
    show_change_link = True
    can_delete = False

    @admin.display(description="Line total")
    def line_total_display(self, obj):
        if not obj.pk:
            return None
        return obj.line_total

    def has_delete_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    fields = ("payment_date", "amount", "method", "reference", "received_by")
    raw_id_fields = ("received_by",)
    extra = 0
    show_change_link = True


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "repair_order",
        "customer_display",
        "status",
        "issued_at",
        "due_date",
        "subtotal",
        "tax_amount",
        "total_amount_display",
        "amount_paid_display",
        "balance_due_display",
    )
    list_filter = ("status", "issued_at", "due_date")
    search_fields = (
        "invoice_number",
        "repair_order__repair_order_number",
        "repair_order__customer__first_name",
        "repair_order__customer__last_name",
        "repair_order__customer__business_name",
        "repair_order__vehicle__vin",
        "repair_order__vehicle__license_plate",
    )
    list_select_related = (
        "repair_order",
        "repair_order__customer",
        "repair_order__vehicle",
        "created_by",
        "updated_by",
    )
    raw_id_fields = ("repair_order", "created_by", "updated_by")
    readonly_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "total_amount_display",
        "amount_paid_display",
        "balance_due_display",
        "is_paid_display",
    )
    inlines = [InvoiceLineItemInline, PaymentInline]
    fieldsets = (
        (
            "Invoice",
            {"fields": ("repair_order", "invoice_number", "status")},
        ),
        (
            "Amounts",
            {
                "fields": (
                    "subtotal",
                    "tax_amount",
                    "total_amount_display",
                    "amount_paid_display",
                    "balance_due_display",
                    "is_paid_display",
                )
            },
        ),
        (
            "Dates",
            {"fields": ("issued_at", "due_date")},
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

    @admin.display(description="Total")
    def total_amount_display(self, obj):
        return obj.total_amount

    @admin.display(description="Paid")
    def amount_paid_display(self, obj):
        return obj.amount_paid

    @admin.display(description="Balance")
    def balance_due_display(self, obj):
        return obj.balance_due

    @admin.display(boolean=True, description="Paid?")
    def is_paid_display(self, obj):
        return obj.is_paid

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InvoiceLineItem)
class InvoiceLineItemAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "item_type",
        "description",
        "quantity",
        "unit_price",
        "line_total_display",
        "created_at",
    )
    list_filter = ("item_type", "created_at")
    search_fields = ("invoice__invoice_number", "description")
    list_select_related = ("invoice", "invoice__repair_order")
    raw_id_fields = ("invoice",)
    readonly_fields = ("created_at", "updated_at", "line_total_display")
    fieldsets = (
        (
            "Line item",
            {"fields": ("invoice", "item_type", "description", "quantity", "unit_price")},
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

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "invoice",
        "payment_date",
        "amount",
        "method",
        "reference",
        "received_by",
        "created_at",
    )
    list_filter = ("method", "payment_date", "created_at")
    search_fields = (
        "invoice__invoice_number",
        "invoice__repair_order__repair_order_number",
        "reference",
        "received_by__username",
        "received_by__email",
    )
    list_select_related = ("invoice", "invoice__repair_order", "received_by")
    raw_id_fields = ("invoice", "received_by")
    readonly_fields = ("created_at",)
    fieldsets = (
        (
            "Payment",
            {"fields": ("invoice", "payment_date", "amount", "method")},
        ),
        (
            "Details",
            {"fields": ("reference", "notes", "received_by")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at",), "classes": ("collapse",)},
        ),
    )

    def save_model(self, request, obj, form, change):
        if not obj.received_by_id:
            obj.received_by = request.user
        super().save_model(request, obj, form, change)
