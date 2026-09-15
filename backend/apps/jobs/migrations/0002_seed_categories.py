from django.db import migrations


def seed_categories(apps, schema_editor):
    JobCategory = apps.get_model("jobs", "JobCategory")
    categories = [
        "Food & Restaurants",
        "Retail / Supermarkets / Marts",
        "Events",
        "Technology",
        "Education",
        "Digital Marketing",
        "Logistics",
        "Local Business",
        "Marketing",
        "Creative / Media",
        "Office / Administration",
        "Seasonal / Festival",
    ]
    for name in categories:
        JobCategory.objects.get_or_create(name=name)


def reverse_seed(apps, schema_editor):
    JobCategory = apps.get_model("jobs", "JobCategory")
    JobCategory.objects.filter(name__in=[
        "Food & Restaurants",
        "Retail / Supermarkets / Marts",
        "Events",
        "Technology",
        "Education",
        "Digital Marketing",
        "Logistics",
        "Local Business",
        "Marketing",
        "Creative / Media",
        "Office / Administration",
        "Seasonal / Festival",
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_seed),
    ]
