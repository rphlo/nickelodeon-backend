# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nickelodeon.models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Song',
            fields=[
                ('id', models.CharField(default=nickelodeon.models.random_key, max_length=12, serialize=False, primary_key=True)),
                ('artist', models.CharField(max_length=255, verbose_name='artist', blank=True)),
                ('title', models.CharField(max_length=255, verbose_name='title', blank=True)),
                ('filename', models.FilePathField(recursive=True, max_length=255, path=b'/home/rphl/projects/django-nickelodeon/nickelodeon/app/media', unique=True, verbose_name='file name', db_index=True)),
            ],
            options={
                'permissions': (('can_listen_songs', 'Can listen songs'),),
            },
        ),
        migrations.CreateModel(
            name='YouTubeDownloadTask',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('video_id', models.CharField(max_length=11, validators=[django.core.validators.RegexValidator(b'^[a-zA-Z0-9_-]{11}$')])),
                ('task_id', models.CharField(unique=True, max_length=50)),
            ],
        ),
    ]
