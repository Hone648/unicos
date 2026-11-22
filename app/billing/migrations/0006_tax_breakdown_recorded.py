from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_backfill_line_item_taxability"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="tax_breakdown_recorded",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AlterField(
            model_name="invoice",
            name="tax_breakdown_recorded",
            field=models.BooleanField(default=True, editable=False),
        ),
    ]
