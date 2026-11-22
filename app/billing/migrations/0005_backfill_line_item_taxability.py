"""Backfill Texas default taxability on existing invoice line items and
recalculate invoice tax snapshots.

Existing line items predate the ``is_taxable`` field. Set the Texas defaults by
item type (labor/sublet/misc -> not taxable; parts/materials -> taxable), then
recompute each affected invoice's taxable subtotal and tax amount so stored
totals stay consistent. Subtotals are unchanged (they already summed all line
items). Payment status is intentionally left untouched here.
"""

from decimal import Decimal

from core.tax import calculate_tax, quantize_money
from django.db import migrations

_TAXABLE_ITEM_TYPES = ("parts", "materials")


def backfill_taxability(apps, schema_editor):
    InvoiceLineItem = apps.get_model("billing", "InvoiceLineItem")
    Invoice = apps.get_model("billing", "Invoice")

    # Parts/materials become taxable; everything else keeps the False default.
    InvoiceLineItem.objects.filter(item_type__in=_TAXABLE_ITEM_TYPES).update(is_taxable=True)

    for invoice in Invoice.objects.all():
        line_items = list(invoice.line_items.all())
        if not line_items:
            continue
        taxable = Decimal("0.00")
        for item in line_items:
            line_total = quantize_money(
                (item.quantity or Decimal("0.00")) * (item.unit_price or Decimal("0.00"))
            )
            if item.is_taxable:
                taxable += line_total
        invoice.taxable_subtotal = quantize_money(taxable)
        invoice.tax_amount = calculate_tax(invoice.taxable_subtotal, invoice.tax_rate or Decimal("0"))
        invoice.save(update_fields=["taxable_subtotal", "tax_amount"])


def unset_taxability(apps, schema_editor):
    InvoiceLineItem = apps.get_model("billing", "InvoiceLineItem")
    InvoiceLineItem.objects.update(is_taxable=False)


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0004_invoice_tax_rate_invoice_taxable_subtotal_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_taxability, unset_taxability),
    ]
