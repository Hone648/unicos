from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


class RepairOrder(models.Model):
    class Status(models.TextChoices):
        INTAKE = "intake", "Intake"
        ESTIMATING = "estimating", "Estimating"
        AWAITING_APPROVAL = "awaiting_approval", "Awaiting approval"
        APPROVED = "approved", "Approved"
        PARTS_ORDERED = "parts_ordered", "Parts ordered"
        IN_REPAIR = "in_repair", "In repair"
        QUALITY_CHECK = "quality_check", "Quality check"
        READY_FOR_PICKUP = "ready_for_pickup", "Ready for pickup"
        DELIVERED = "delivered", "Delivered"
        CLOSED = "closed", "Closed"
        CANCELED = "canceled", "Canceled"

    repair_order_number = models.CharField(max_length=30, unique=True, db_index=True)

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="repair_orders",
    )
    vehicle = models.ForeignKey(
        "vehicles.Vehicle",
        on_delete=models.PROTECT,
        related_name="repair_orders",
    )

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.INTAKE,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_repair_orders",
    )

    opened_at = models.DateTimeField(default=timezone.now)
    promised_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    reported_problem = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_repair_orders",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_repair_orders",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-opened_at", "-id"]

    def clean(self):
        # Ensure the selected vehicle belongs to the selected customer.
        if self.vehicle_id and self.customer_id:
            if self.vehicle.customer_id != self.customer_id:
                raise ValidationError(
                    "The selected vehicle does not belong to the selected customer."
                )

    @property
    def is_closed(self):
        return self.status in {self.Status.CLOSED, self.Status.CANCELED}

    def set_status(self, new_status, *, changed_by=None, note=""):
        """Change status and record history. No-op if status is unchanged.

        Raises ValidationError for values outside RepairOrder.Status.
        """
        if new_status not in self.Status.values:
            raise ValidationError(
                f"'{new_status}' is not a valid repair order status."
            )
        if new_status == self.status:
            return
        # _status_changed_by / _status_change_note are read by save() to
        # populate the status history record rather than requiring the caller
        # to manage history directly.
        self._status_changed_by = changed_by
        self._status_change_note = note
        self.status = new_status
        self.save()

    def _clear_status_change_context(self):
        """Remove transient set_status attributes so they cannot leak into a later save."""
        self.__dict__.pop("_status_changed_by", None)
        self.__dict__.pop("_status_change_note", None)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            is_new = self.pk is None
            old_status = None

            if not is_new:
                old_status = (
                    RepairOrder.objects.filter(pk=self.pk)
                    .values_list("status", flat=True)
                    .first()
                )

            super().save(*args, **kwargs)

            # Determine who triggered this status change, then clear the
            # transient attributes so they do not bleed into a later save.
            explicit_changer = getattr(self, "_status_changed_by", None)
            explicit_note = getattr(self, "_status_change_note", "")
            try:
                if is_new:
                    RepairOrderStatusHistory.objects.create(
                        repair_order=self,
                        previous_status=None,
                        new_status=self.status,
                        changed_by=explicit_changer if explicit_changer is not None else self.created_by,
                        note=explicit_note,
                    )
                elif old_status is not None and old_status != self.status:
                    RepairOrderStatusHistory.objects.create(
                        repair_order=self,
                        previous_status=old_status,
                        new_status=self.status,
                        changed_by=explicit_changer if explicit_changer is not None else self.updated_by,
                        note=explicit_note,
                    )
            finally:
                self._clear_status_change_context()

    def __str__(self):
        return f"RO {self.repair_order_number} - {self.vehicle}"


class RepairOrderStatusHistory(models.Model):
    repair_order = models.ForeignKey(
        RepairOrder,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    previous_status = models.CharField(
        max_length=30,
        choices=RepairOrder.Status.choices,
        null=True,
        blank=True,
    )
    new_status = models.CharField(
        max_length=30,
        choices=RepairOrder.Status.choices,
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="repair_order_status_changes",
    )
    changed_at = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["-changed_at", "-id"]
        indexes = [
            models.Index(fields=["repair_order", "-changed_at"]),
        ]

    def __str__(self):
        prev = self.previous_status or "—"
        return f"RO {self.repair_order_id}: {prev} → {self.new_status}"
