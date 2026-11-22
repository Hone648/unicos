from decimal import Decimal

from core.tax import (
    calculate_tax,
    default_sales_tax_rate,
    quantize_money,
)
from core.tax_review import TAX_REVIEW_REQUIRED, validate_line_tax_edit
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction


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

    class ApprovalSource(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        INSURER = "insurer", "Insurer"
        CUSTOMER_AND_INSURER = "customer_and_insurer", "Customer and insurer"
        OTHER = "other", "Other"

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
    # Tax snapshot: rate captured at creation time plus derived taxable
    # subtotal and tax amount. estimated_total stays the pre-tax subtotal.
    tax_rate = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=default_sales_tax_rate,
    )
    taxable_subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    # Existing documents may carry saved tax without a verified breakdown.
    tax_breakdown_recorded = models.BooleanField(default=True, editable=False)
    notes = models.TextField(blank=True)
    approval_source = models.CharField(
        max_length=30,
        choices=ApprovalSource.choices,
        blank=True,
    )
    approval_contact_name = models.CharField(max_length=200, blank=True)
    approval_reference = models.CharField(max_length=200, blank=True)
    approval_note = models.TextField(blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

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
        if self.tax_rate is not None and self.tax_rate < Decimal("0"):
            raise ValidationError("Tax rate cannot be negative.")
        if self.tax_rate is not None and self.tax_rate > Decimal("1"):
            raise ValidationError("Tax rate cannot exceed 1 (100%).")
        if self.taxable_subtotal is not None and self.taxable_subtotal < Decimal("0.00"):
            raise ValidationError("Taxable subtotal cannot be negative.")
        if self.tax_amount is not None and self.tax_amount < Decimal("0.00"):
            raise ValidationError("Tax amount cannot be negative.")

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

    @property
    def has_approval_capture(self):
        return bool(self.approval_source and self.approval_contact_name and self.approved_at)

    @property
    def total_amount(self):
        """Pre-tax subtotal plus estimated sales tax."""
        return (self.estimated_total or Decimal("0.00")) + (self.tax_amount or Decimal("0.00"))

    @property
    def customer_responsibility(self):
        """Grand total less the deductible, never below zero."""
        responsibility = self.total_amount - (self.deductible or Decimal("0.00"))
        return max(responsibility, Decimal("0.00"))

    @property
    def tax_rate_percent(self):
        """Tax rate expressed as a percentage for display (e.g. 8.250)."""
        return (self.tax_rate or Decimal("0")) * Decimal("100")

    def recalculate_total(self):
        """Recalculate line totals and keep saved tax on historical estimates."""
        line_items = list(self.line_items.all())
        total = sum((line_item.line_total for line_item in line_items), Decimal("0.00"))
        self.estimated_total = quantize_money(total)
        update_fields = ["estimated_total", "updated_at"]
        if self.tax_breakdown_recorded:
            taxable = sum(
                (line_item.line_total for line_item in line_items if line_item.is_taxable),
                Decimal("0.00"),
            )
            self.taxable_subtotal = quantize_money(taxable)
            self.tax_amount = calculate_tax(self.taxable_subtotal, self.tax_rate or Decimal("0"))
            update_fields.extend(["taxable_subtotal", "tax_amount"])
        self.save(update_fields=update_fields)

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
    # Whether this line contributes to the taxable subtotal. Defaults to False
    # at the model level; forms seed the Texas default from item_type so an
    # explicitly chosen value is never silently overridden.
    is_taxable = models.BooleanField(default=False)
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

    def validate_tax_edit(self):
        if self.estimate_id:
            validate_line_tax_edit(self, self.estimate, "estimate_id")

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.estimate_id:
            tax_was_reviewed = self.estimate.tax_breakdown_recorded
            self.estimate.refresh_from_db(from_queryset=Estimate.objects.select_for_update())
            # A form opened before review has no taxability field. Keep the
            # reviewed value if review completed while that form was saving.
            if self.pk and not tax_was_reviewed and self.estimate.tax_breakdown_recorded:
                self.is_taxable = (
                    type(self).objects.values_list("is_taxable", flat=True).get(pk=self.pk)
                )
        self.validate_tax_edit()
        self.full_clean()
        super().save(*args, **kwargs)
        if self.estimate.tax_breakdown_recorded:
            self.estimate.recalculate_total()

    @transaction.atomic
    def delete(self, *args, **kwargs):
        estimate = Estimate.objects.select_for_update().get(pk=self.estimate_id)
        if not estimate.tax_breakdown_recorded:
            raise ValidationError(TAX_REVIEW_REQUIRED)
        super().delete(*args, **kwargs)
        estimate.recalculate_total()

    def __str__(self):
        return f"{self.get_item_type_display()}: {self.description}"
