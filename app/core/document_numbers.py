import re

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import DocumentNumberSequence

_RO_PATTERN = re.compile(r"^RO-(\d{4})-(\d{6})$")
_INV_PATTERN = re.compile(r"^INV-(\d{4})-(\d{6})$")
_EST_PATTERN = re.compile(r"^EST-(\d{4})-(\d{6})$")


def _find_max_existing(document_type, year):
    year_str = str(year)
    if document_type == DocumentNumberSequence.DocumentType.REPAIR_ORDER:
        from repair_orders.models import RepairOrder

        numbers = RepairOrder.objects.values_list("repair_order_number", flat=True)
        pattern = _RO_PATTERN
    elif document_type == DocumentNumberSequence.DocumentType.ESTIMATE:
        from estimates.models import Estimate

        numbers = Estimate.objects.values_list("estimate_number", flat=True)
        pattern = _EST_PATTERN
    else:
        from billing.models import Invoice

        numbers = Invoice.objects.values_list("invoice_number", flat=True)
        pattern = _INV_PATTERN

    max_val = 0
    for num in numbers:
        m = pattern.match(num)
        if m and m.group(1) == year_str:
            val = int(m.group(2))
            if val > max_val:
                max_val = val
    return max_val


def _generate_number(document_type, prefix):
    year = timezone.localdate().year

    with transaction.atomic():
        try:
            seq = DocumentNumberSequence.objects.select_for_update().get(
                document_type=document_type, year=year
            )
        except DocumentNumberSequence.DoesNotExist:
            max_existing = _find_max_existing(document_type, year)
            try:
                with transaction.atomic():  # savepoint to handle first-row race condition
                    seq = DocumentNumberSequence.objects.create(
                        document_type=document_type,
                        year=year,
                        last_value=max_existing,
                    )
            except IntegrityError:
                seq = DocumentNumberSequence.objects.select_for_update().get(
                    document_type=document_type, year=year
                )

        seq.last_value += 1
        seq.save(update_fields=["last_value", "updated_at"])
        return f"{prefix}-{year}-{seq.last_value:06d}"


def generate_repair_order_number():
    return _generate_number(DocumentNumberSequence.DocumentType.REPAIR_ORDER, "RO")


def generate_invoice_number():
    return _generate_number(DocumentNumberSequence.DocumentType.INVOICE, "INV")


def generate_estimate_number():
    return _generate_number(DocumentNumberSequence.DocumentType.ESTIMATE, "EST")
