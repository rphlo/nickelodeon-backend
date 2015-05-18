# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nickelodeon', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='song',
            name='filename',
            field=models.FilePathField(recursive=True, max_length=255, path=b'/home/rphl/projects/django-nickelodeon/nickelodeon/site/media', unique=True, verbose_name='file name', db_index=True),
        ),
    ]
