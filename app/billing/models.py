from decimal import Decimal

from core.tax import (
    calculate_tax,
    default_sales_tax_rate,
    quantize_money,
)
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PARTIALLY_PAID = "partially_paid", "Partially paid"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    repair_order = models.OneToOneField(
        "repair_orders.RepairOrder",
        on_delete=models.PROTECT,
        related_name="invoice",
    )
    invoice_number = models.CharField(max_length=30, unique=True, db_index=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    source_estimate = models.ForeignKey(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="converted_invoices",
        help_text="The approved estimate this invoice was created from, if any.",
    )
    issued_at = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    # Tax snapshot: rate captured at creation time (or copied from the source
    # estimate) plus the derived taxable subtotal. subtotal stays pre-tax.
    tax_rate = models.DecimalField(
        max_digits=6,
        decimal_places=5,
        default=default_sales_tax_rate,
    )
    taxable_subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_estimate"],
                condition=models.Q(source_estimate__isnull=False),
                name="unique_invoice_source_estimate",
            ),
        ]

    def clean(self):
        if self.subtotal is not None and self.subtotal < Decimal("0.00"):
            raise ValidationError("Subtotal cannot be negative.")
        if self.tax_amount is not None and self.tax_amount < Decimal("0.00"):
            raise ValidationError("Tax amount cannot be negative.")
        if self.tax_rate is not None and self.tax_rate < Decimal("0"):
            raise ValidationError("Tax rate cannot be negative.")
        if self.tax_rate is not None and self.tax_rate > Decimal("1"):
            raise ValidationError("Tax rate cannot exceed 1 (100%).")
        if self.taxable_subtotal is not None and self.taxable_subtotal < Decimal("0.00"):
            raise ValidationError("Taxable subtotal cannot be negative.")
        if self.issued_at and self.due_date and self.due_date < self.issued_at:
            raise ValidationError("Due date cannot be before the issued date.")

    @property
    def total_amount(self):
        return (self.subtotal or Decimal("0.00")) + (self.tax_amount or Decimal("0.00"))

    @property
    def tax_rate_percent(self):
        """Tax rate expressed as a percentage for display (e.g. 8.250)."""
        return (self.tax_rate or Decimal("0")) * Decimal("100")

    @property
    def amount_paid(self):
        result = self.payments.aggregate(total=models.Sum("amount"))["total"]
        return result or Decimal("0.00")

    @property
    def balance_due(self):
        balance = self.total_amount - self.amount_paid
        return max(balance, Decimal("0.00"))

    @property
    def is_paid(self):
        return self.balance_due == Decimal("0.00") and self.total_amount > Decimal("0.00")

    def sync_payment_status(self):
        """Update invoice status based on current payments. Void invoices are never touched."""
        if self.status == self.Status.VOID:
            return
        paid = self.amount_paid
        total = self.total_amount

        if total > Decimal("0.00") and paid >= total:
            new_status = self.Status.PAID
        elif paid > Decimal("0.00"):
            new_status = self.Status.PARTIALLY_PAID
        elif self.status in {self.Status.PAID, self.Status.PARTIALLY_PAID}:
            # Payments were removed — fall back to ISSUED if the invoice was
            # already issued (issued_at is set), otherwise fall back to DRAFT.
            new_status = self.Status.ISSUED if self.issued_at else self.Status.DRAFT
        else:
            # No payments and already DRAFT/ISSUED — nothing to change.
            return

        if new_status != self.status:
            self.status = new_status
            self.save(update_fields=["status", "updated_at"])

    def recalculate_subtotal_from_line_items(self):
        """Recalculate subtotal, taxable subtotal, and tax from line items.

        ``subtotal`` sums all line items; ``taxable_subtotal`` sums only taxable
        line items; ``tax_amount`` applies the snapshotted ``tax_rate``. Payment
        status is synced afterward, matching the prior behavior.
        """
        line_items = list(self.line_items.all())
        total = sum((line_item.line_total for line_item in line_items), Decimal("0.00"))
        taxable = sum(
            (line_item.line_total for line_item in line_items if line_item.is_taxable),
            Decimal("0.00"),
        )
        self.subtotal = quantize_money(total)
        self.taxable_subtotal = quantize_money(taxable)
        self.tax_amount = calculate_tax(self.taxable_subtotal, self.tax_rate or Decimal("0"))
        if self.amount_paid > self.total_amount:
            raise ValidationError(
                "Invoice line items cannot total less than the amount already paid."
            )
        self.save(update_fields=["subtotal", "taxable_subtotal", "tax_amount", "updated_at"])
        self.sync_payment_status()

    def __str__(self):
        return f"Invoice {self.invoice_number}"


class InvoiceLineItem(models.Model):
    class ItemType(models.TextChoices):
        LABOR = "labor", "Labor"
        PARTS = "parts", "Parts"
        MATERIALS = "materials", "Materials"
        SUBLET = "sublet", "Sublet"
        MISC = "misc", "Misc"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="line_items",
    )
    item_type = models.CharField(max_length=20, choices=ItemType.choices)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    # Whether this line contributes to the taxable subtotal. Defaults to False
    # at the model level; forms seed the Texas default from item_type.
    is_taxable = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    @property
    def line_total(self):
        total = (self.quantity or Decimal("0.00")) * (self.unit_price or Decimal("0.00"))
        return total.quantize(Decimal("0.01"))

    def clean(self):
        if not self.invoice_id:
            return

        others = list(self.invoice.line_items.exclude(pk=self.pk))
        existing_total = sum((line_item.line_total for line_item in others), Decimal("0.00"))
        existing_taxable = sum(
            (line_item.line_total for line_item in others if line_item.is_taxable),
            Decimal("0.00"),
        )
        projected_subtotal = existing_total + self.line_total
        projected_taxable = existing_taxable + (
            self.line_total if self.is_taxable else Decimal("0.00")
        )
        projected_tax = calculate_tax(projected_taxable, self.invoice.tax_rate or Decimal("0"))
        projected_total = projected_subtotal + projected_tax
        if self.invoice.amount_paid > projected_total:
            raise ValidationError(
                "Line item changes cannot make the invoice total less than the amount already paid."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        self.invoice.recalculate_subtotal_from_line_items()

    def __str__(self):
        return f"{self.get_item_type_display()}: {self.description}"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CHECK = "check", "Check"
        CARD = "card", "Card"
        ACH = "ach", "ACH"
        OTHER = "other", "Other"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=10, choices=Method.choices, default=Method.CASH)
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]

    def clean(self):
        if self.amount is not None and self.amount <= Decimal("0.00"):
            raise ValidationError("Payment amount must be greater than zero.")

        if self.invoice_id:
            invoice = self.invoice
            if invoice.status == Invoice.Status.VOID:
                raise ValidationError("Cannot add a payment to a void invoice.")

            # Balance check: sum existing payments excluding this one (for updates).
            existing = invoice.payments.exclude(pk=self.pk).aggregate(total=models.Sum("amount"))[
                "total"
            ] or Decimal("0.00")
            if self.amount is not None and existing + self.amount > invoice.total_amount:
                raise ValidationError(
                    "Payment would exceed the invoice balance. "
                    f"Balance remaining: {invoice.total_amount - existing:.2f}."
                )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.sync_payment_status()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.sync_payment_status()

    def __str__(self):
        return f"{self.get_method_display()} payment {self.amount} for {self.invoice}"
