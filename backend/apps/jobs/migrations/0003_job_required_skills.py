from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jobs", "0002_seed_categories"),
        ("profiles", "0002_studentprofile_skills"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="required_skills",
            field=models.ManyToManyField(blank=True, related_name="jobs", to="profiles.skill"),
        ),
    ]
