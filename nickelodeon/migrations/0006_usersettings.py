# Generated by Django 3.2.11 on 2022-01-17 17:46

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import nickelodeon.utils


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("nickelodeon", "0005_auto_20210714_1126"),
    ]

    operations = [
        migrations.CreateModel(
            name="UserSettings",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "storage_prefix",
                    models.CharField(
                        default=nickelodeon.utils.random_key, max_length=32
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "user settings",
                "verbose_name_plural": "user settings",
            },
        ),
    ]
