# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('nickelodeon', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='song',
            name='filename',
            field=models.FilePathField(
                recursive=True, max_length=255,
                path=settings.MEDIA_ROOT, unique=True,
                verbose_name='file name', db_index=True
            ),
            preserve_default=True,
        ),
    ]
