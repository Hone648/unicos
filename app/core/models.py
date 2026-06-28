from django.db import models


class DocumentNumberSequence(models.Model):
    class DocumentType(models.TextChoices):
        REPAIR_ORDER = "repair_order", "Repair Order"
        INVOICE = "invoice", "Invoice"

    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    year = models.PositiveSmallIntegerField()
    last_value = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("document_type", "year")]
        ordering = ["document_type", "year"]

    def __str__(self):
        return f"{self.document_type}/{self.year}: {self.last_value}"
