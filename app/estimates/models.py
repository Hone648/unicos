from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Estimate(models.Model):
    """Estimate / insurance-claim context attached to a repair order.

    A repair order may carry multiple estimates. An estimate may be an initial
    estimate or a supplement (``kind="supplement"``) that links back to a parent
    estimate via ``parent_estimate``. Estimates carry their own line items, which
    drive ``estimated_total`` once any exist. Invoice generation, approval, PDF,
    and signature workflows remain out of scope.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"

    class Kind(models.TextChoices):
        INITIAL = "initial", "Initial"
        SUPPLEMENT = "supplement", "Supplement"

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
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.INITIAL,
    )
    parent_estimate = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="supplements",
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

        # Supplement lineage rules.
        if self.kind == self.Kind.INITIAL and self.parent_estimate_id:
            raise ValidationError("An initial estimate cannot have a parent estimate.")
        if self.kind == self.Kind.SUPPLEMENT and not self.parent_estimate_id:
            raise ValidationError("A supplement estimate must have a parent estimate.")
        if self.parent_estimate_id and self.pk and self.parent_estimate_id == self.pk:
            raise ValidationError("An estimate cannot be its own parent.")
        if (
            self.parent_estimate_id
            and self.repair_order_id
            and self.parent_estimate.repair_order_id != self.repair_order_id
        ):
            raise ValidationError(
                "A supplement must belong to the same repair order as its parent estimate."
            )

    @property
    def has_line_items(self):
        return self.line_items.exists()

    @property
    def is_supplement(self):
        return self.kind == self.Kind.SUPPLEMENT

    def recalculate_total(self):
        """Sum line items into estimated_total. Resets to 0.00 when none remain."""
        total = sum(
            (line_item.line_total for line_item in self.line_items.all()),
            Decimal("0.00"),
        )
        self.estimated_total = total.quantize(Decimal("0.01"))
        self.save(update_fields=["estimated_total", "updated_at"])

    def __str__(self):
        return f"Estimate {self.estimate_number}"


class EstimateLineItem(models.Model):
    class ItemType(models.TextChoices):
        LABOR = "labor", "Labor"
        PARTS = "parts", "Parts"
        MATERIALS = "materials", "Materials"
        SUBLET = "sublet", "Sublet"
        MISC = "misc", "Misc"

    estimate = models.ForeignKey(
        Estimate,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    item_type = models.CharField(
        max_length=20,
        choices=ItemType.choices,
        default=ItemType.LABOR,
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]

    @property
    def line_total(self):
        total = (self.quantity or Decimal("0.00")) * (self.unit_price or Decimal("0.00"))
        return total.quantize(Decimal("0.01"))

    def clean(self):
        if self.description is not None and not self.description.strip():
            raise ValidationError({"description": "Description is required."})
        if self.quantity is not None and self.quantity <= Decimal("0.00"):
            raise ValidationError({"quantity": "Quantity must be greater than zero."})
        if self.unit_price is not None and self.unit_price < Decimal("0.00"):
            raise ValidationError({"unit_price": "Unit price cannot be negative."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.estimate.recalculate_total()

    def delete(self, *args, **kwargs):
        estimate = self.estimate
        super().delete(*args, **kwargs)
        estimate.recalculate_total()

    def __str__(self):
        return f"{self.get_item_type_display()}: {self.description}"
