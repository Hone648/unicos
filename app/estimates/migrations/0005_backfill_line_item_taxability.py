"""Backfill Texas default taxability on existing estimate line items and
recalculate estimate tax snapshots.

Existing line items predate the ``is_taxable`` field. Set the Texas defaults by
item type (labor/sublet/misc -> not taxable; parts/materials -> taxable), then
recompute each affected estimate's taxable subtotal and tax amount so stored
totals stay consistent. Estimated totals are unchanged (they already summed all
line items).
"""

from decimal import Decimal

from core.tax import calculate_tax, quantize_money
from django.db import migrations

_TAXABLE_ITEM_TYPES = ("parts", "materials")


def backfill_taxability(apps, schema_editor):
    EstimateLineItem = apps.get_model("estimates", "EstimateLineItem")
    Estimate = apps.get_model("estimates", "Estimate")

    # Parts/materials become taxable; everything else keeps the False default.
    EstimateLineItem.objects.filter(item_type__in=_TAXABLE_ITEM_TYPES).update(is_taxable=True)

    # Recompute tax snapshot for every estimate that has line items.
    for estimate in Estimate.objects.all():
        line_items = list(estimate.line_items.all())
        if not line_items:
            continue
        taxable = Decimal("0.00")
        for item in line_items:
            line_total = quantize_money(
                (item.quantity or Decimal("0.00")) * (item.unit_price or Decimal("0.00"))
            )
            if item.is_taxable:
                taxable += line_total
        estimate.taxable_subtotal = quantize_money(taxable)
        estimate.tax_amount = calculate_tax(estimate.taxable_subtotal, estimate.tax_rate or Decimal("0"))
        estimate.save(update_fields=["taxable_subtotal", "tax_amount"])


def unset_taxability(apps, schema_editor):
    EstimateLineItem = apps.get_model("estimates", "EstimateLineItem")
    EstimateLineItem.objects.update(is_taxable=False)


class Migration(migrations.Migration):
    dependencies = [
        ("estimates", "0004_estimate_tax_amount_estimate_tax_rate_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_taxability, unset_taxability),
    ]
