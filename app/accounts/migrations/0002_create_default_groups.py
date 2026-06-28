from django.db import migrations

# Baseline staff role groups. Group names only for this slice; no
# domain-specific permissions are assigned yet because domain models do not
# exist. See docs/DECISIONS/0005-custom-user-model.md.
DEFAULT_GROUPS = [
    "Owner/Admin",
    "Manager",
    "Front Desk",
    "Estimator",
    "Technician",
    "Read-only",
]


def create_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in DEFAULT_GROUPS:
        Group.objects.get_or_create(name=name)


def remove_default_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=DEFAULT_GROUPS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_groups, remove_default_groups),
    ]
