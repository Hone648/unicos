from django.contrib import admin

from .models import CommunicationEntry


@admin.register(CommunicationEntry)
class CommunicationEntryAdmin(admin.ModelAdmin):
    list_display = (
        "repair_order",
        "occurred_at",
        "direction",
        "channel",
        "contact_role",
        "contact_name",
        "is_authorization_related",
        "created_by",
        "created_at",
    )
    list_filter = (
        "direction",
        "channel",
        "contact_role",
        "is_authorization_related",
        "occurred_at",
    )
    search_fields = (
        "repair_order__repair_order_number",
        "contact_name",
        "summary",
        "next_step",
    )
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("repair_order", "created_by")
