from django.contrib import admin, messages

from .models import Invoice, InvoiceLineItem, Payment
from .services import (
    InvoiceIssueBlocked,
    InvoiceLineItemMutationBlocked,
    InvoiceVoidBlocked,
    PaymentRecordingBlocked,
    create_invoice_line_item,
    edit_invoice_line_item,
    issue_invoice,
    record_payment,
    void_invoice,
)


class InvoiceLineItemInline(admin.TabularInline):
    """Read-only: line-item mutation must go through InvoiceLineItemAdmin,
    which routes saves through the billing service layer."""

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

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    """Read-only: payment creation must go through PaymentAdmin, which routes
    saves through the billing service layer."""

    model = Payment
    fields = ("payment_date", "amount", "method", "reference", "received_by")
    raw_id_fields = ("received_by",)
    extra = 0
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
        "source_estimate",
        "created_by",
        "updated_by",
    )
    raw_id_fields = ("repair_order", "source_estimate", "created_by", "updated_by")
    readonly_fields = (
        "status",
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
    actions = ["issue_selected_invoices", "void_selected_invoices"]
    fieldsets = (
        (
            "Invoice",
            {"fields": ("repair_order", "invoice_number", "status", "source_estimate")},
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

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.line_items.exists():
            readonly.append("subtotal")
        return readonly

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def _apply_invoice_action(self, request, queryset, service_fn, blocked_exc, label):
        updated = 0
        blocked = 0
        for invoice in queryset:
            try:
                service_fn(invoice, actor=request.user)
                updated += 1
            except blocked_exc as exc:
                blocked += 1
                self.message_user(request, str(exc), level=messages.ERROR)
        if updated:
            self.message_user(request, f"{updated} invoice(s) {label}.")
        if blocked:
            self.message_user(
                request,
                f"{blocked} invoice(s) could not be {label} due to billing rules.",
                level=messages.WARNING,
            )

    @admin.action(description="Issue selected invoices")
    def issue_selected_invoices(self, request, queryset):
        self._apply_invoice_action(request, queryset, issue_invoice, InvoiceIssueBlocked, "issued")

    @admin.action(description="Void selected invoices")
    def void_selected_invoices(self, request, queryset):
        self._apply_invoice_action(request, queryset, void_invoice, InvoiceVoidBlocked, "voided")


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

    def save_model(self, request, obj, form, change):
        data = {
            "item_type": obj.item_type,
            "description": obj.description,
            "quantity": obj.quantity,
            "unit_price": obj.unit_price,
        }
        try:
            if change:
                edit_invoice_line_item(obj, data, actor=request.user)
            else:
                created = create_invoice_line_item(obj.invoice, data, actor=request.user)
                obj.pk = created.pk
                obj.refresh_from_db()
        except InvoiceLineItemMutationBlocked as exc:
            self.message_user(request, str(exc), level=messages.ERROR)


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

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change:
            # Existing payments are immutable through admin; has_change_permission
            # already blocks reaching this point. Guard defensively against
            # direct calls (e.g. from tests) that bypass the permission check.
            return
        data = {
            "payment_date": obj.payment_date,
            "amount": obj.amount,
            "method": obj.method,
            "reference": obj.reference,
            "notes": obj.notes,
        }
        try:
            created = record_payment(obj.invoice, data, actor=request.user)
        except PaymentRecordingBlocked as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return
        obj.pk = created.pk
        obj.refresh_from_db()
