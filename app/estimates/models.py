from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Estimate(models.Model):
    """Estimate / insurance-claim context attached to a repair order.

    A repair order may carry multiple estimates (revisions, supplements later).
    This slice captures only basic status and insurance/claim fields; estimate
    line items, supplements, approval workflow, and invoice generation are
    intentionally out of scope.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"

    repair_order = models.ForeignKey(
        "repair_orders.RepairOrder",
        on_delete=models.PROTECT,
        related_name="estimates",
    )
    estimate_number = models.CharField(max_length=32, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    insurance_company = models.CharField(max_length=200, blank=True)
    claim_number = models.CharField(max_length=100, blank=True)
    deductible = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    estimated_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_estimates",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_estimates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def clean(self):
        if self.deductible is not None and self.deductible < Decimal("0.00"):
            raise ValidationError("Deductible cannot be negative.")
        if self.estimated_total is not None and self.estimated_total < Decimal("0.00"):
            raise ValidationError("Estimated total cannot be negative.")

    def __str__(self):
        return f"Estimate {self.estimate_number}"
