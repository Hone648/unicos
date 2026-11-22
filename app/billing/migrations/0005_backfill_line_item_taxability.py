"""Preserve the published migration ID without rewriting saved tax amounts."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0004_invoice_tax_rate_invoice_taxable_subtotal_and_more"),
    ]

    operations = []
