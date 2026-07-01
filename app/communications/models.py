from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

_FUTURE_SKEW_SECONDS = 5 * 60


class CommunicationEntry(models.Model):
    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"
        INTERNAL = "internal", "Internal"

    class Channel(models.TextChoices):
        PHONE = "phone", "Phone"
        EMAIL = "email", "Email"
        TEXT = "text", "Text"
        IN_PERSON = "in_person", "In person"
        INSURER_PORTAL = "insurer_portal", "Insurer portal"
        OTHER = "other", "Other"

    class ContactRole(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        INSURER = "insurer", "Insurer"
        ADJUSTER = "adjuster", "Adjuster"
        SHOP_INTERNAL = "shop_internal", "Shop internal"
        VENDOR = "vendor", "Vendor"
        TOW_PROVIDER = "tow_provider", "Tow provider"
        OTHER = "other", "Other"

    repair_order = models.ForeignKey(
        "repair_orders.RepairOrder",
        on_delete=models.PROTECT,
        related_name="communications",
    )
    direction = models.CharField(max_length=20, choices=Direction.choices)
    channel = models.CharField(max_length=20, choices=Channel.choices)
    contact_role = models.CharField(max_length=20, choices=ContactRole.choices)
    contact_name = models.CharField(max_length=120, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    summary = models.TextField()
    next_step = models.CharField(max_length=255, blank=True)
    is_authorization_related = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_communication_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["repair_order", "occurred_at"]),
        ]
        verbose_name_plural = "communication entries"

    def clean(self):
        super().clean()
        self.contact_name = (self.contact_name or "").strip()
        self.summary = (self.summary or "").strip()
        self.next_step = (self.next_step or "").strip()

        errors = {}
        if not self.summary:
            errors["summary"] = "Summary is required."

        if self.direction != self.Direction.INTERNAL and not self.contact_name:
            errors["contact_name"] = "Contact name is required unless the direction is internal."

        if self.occurred_at:
            future_limit = timezone.now() + timedelta(seconds=_FUTURE_SKEW_SECONDS)
            if self.occurred_at > future_limit:
                errors["occurred_at"] = (
                    "Communication time cannot be more than 5 minutes in the future."
                )

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        occurred_date = self.occurred_at.date().isoformat() if self.occurred_at else "unknown date"
        return (
            f"{self.repair_order.repair_order_number}: "
            f"{self.get_direction_display()} {self.get_channel_display()} on {occurred_date}"
        )
