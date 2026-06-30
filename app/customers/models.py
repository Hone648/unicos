from django.core.exceptions import ValidationError
from django.db import models


class Customer(models.Model):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        BUSINESS = "business", "Business"

    customer_type = models.CharField(
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.INDIVIDUAL,
    )

    # Individual identity
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)

    # Business identity
    business_name = models.CharField(max_length=200, blank=True)

    # Contact
    phone_primary = models.CharField(max_length=30, blank=True)
    phone_secondary = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)

    # Address
    address_line_1 = models.CharField(max_length=200, blank=True)
    address_line_2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)

    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "business_name"]

    def clean(self):
        if self.customer_type == self.CustomerType.INDIVIDUAL:
            if not self.first_name.strip() and not self.last_name.strip():
                raise ValidationError(
                    "Individual customers must have at least a first name or last name."
                )
        elif self.customer_type == self.CustomerType.BUSINESS:
            if not self.business_name.strip():
                raise ValidationError("Business customers must have a business name.")

    @property
    def display_name(self):
        if self.customer_type == self.CustomerType.BUSINESS:
            return self.business_name or "(unnamed business)"
        parts = [self.first_name, self.last_name]
        name = " ".join(p for p in parts if p).strip()
        return name or "(unnamed customer)"

    def __str__(self):
        return self.display_name
