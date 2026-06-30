import os
import uuid

from django.conf import settings
from django.db import models


def _attachment_upload_to(instance, filename):
    safe_basename = os.path.basename(filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_basename}"
    return f"repair_orders/{instance.repair_order_id}/{unique_name}"


class Attachment(models.Model):
    class Category(models.TextChoices):
        PHOTO = "photo", "Photo"
        ESTIMATE = "estimate", "Estimate"
        INVOICE = "invoice", "Invoice"
        AUTHORIZATION = "authorization", "Authorization"
        OTHER = "other", "Other"

    repair_order = models.ForeignKey(
        "repair_orders.RepairOrder",
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    file = models.FileField(upload_to=_attachment_upload_to)
    original_filename = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )
    description = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_attachments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.original_filename} ({self.repair_order.repair_order_number})"
