import re

from django.core.exceptions import ValidationError
from django.db import models

# Standard VIN: 17 chars, uppercase alphanumeric, excluding I, O, Q.
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def validate_vin(value):
    if not VIN_RE.match(value):
        raise ValidationError(
            "Enter a valid 17-character VIN (letters A-Z excluding I, O, Q; digits 0-9)."
        )


class Vehicle(models.Model):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="vehicles",
    )

    vin = models.CharField(
        max_length=17,
        unique=True,
        db_index=True,
        validators=[validate_vin],
        help_text="17-character Vehicle Identification Number (uppercase, no I/O/Q).",
    )

    year = models.PositiveSmallIntegerField(null=True, blank=True)
    make = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    trim = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=50, blank=True)

    license_plate = models.CharField(max_length=20, blank=True)
    license_state = models.CharField(max_length=50, blank=True)

    odometer = models.PositiveIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["make", "model", "vin"]

    def clean_fields(self, exclude=None):
        # Normalize VIN before field validators run so a lowercase or
        # whitespace-padded VIN passes validate_vin without manual correction.
        # clean() runs *after* clean_fields(), so normalization must happen here
        # to be visible to the vin validator that fires inside super().
        if self.vin:
            self.vin = self.vin.strip().upper()
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        # Defensive fallback: normalize even when full_clean() is skipped
        # (e.g. direct ORM saves that bypass form/model validation).
        if self.vin:
            self.vin = self.vin.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        year_part = str(self.year) if self.year else ""
        identity = " ".join(p for p in [year_part, self.make, self.model] if p)
        return f"{identity} ({self.vin})" if identity else self.vin
