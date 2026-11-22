"""Preserve the published migration ID without rewriting saved tax amounts."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("estimates", "0004_estimate_tax_amount_estimate_tax_rate_and_more"),
    ]

    operations = []
