# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-03-04 06:43
from __future__ import unicode_literals

from django.db import migrations, models

import nickelodeon.models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="MP3Song",
            fields=[
                (
                    "id",
                    models.CharField(
                        default=nickelodeon.models.random_key,
                        max_length=12,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "filename",
                    models.CharField(
                        db_index=True,
                        max_length=255,
                        unique=True,
                        verbose_name="file name",
                    ),
                ),
            ],
        ),
    ]
