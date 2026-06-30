from django.contrib import admin

from .models import Attachment


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "original_filename",
        "repair_order",
        "category",
        "size_bytes",
        "uploaded_by",
        "created_at",
    )
    list_filter = ("category", "created_at")
    search_fields = (
        "original_filename",
        "description",
        "repair_order__repair_order_number",
    )
    readonly_fields = (
        "repair_order",
        "file",
        "original_filename",
        "content_type",
        "size_bytes",
        "uploaded_by",
        "created_at",
    )
    list_select_related = ("repair_order", "uploaded_by")

    def has_delete_permission(self, request, obj=None):
        return False
