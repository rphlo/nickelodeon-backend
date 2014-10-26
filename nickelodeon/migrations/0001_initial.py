# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.conf import settings
from django.db import models, migrations
import common_base.core.fields
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Song',
            fields=[
                ('uuid', common_base.core.fields.ShortUuidField(primary_key=True, serialize=False, editable=False, verbose_name='id')),
                ('artist', models.CharField(max_length=255, verbose_name='artist', blank=True)),
                ('title', models.CharField(max_length=255, verbose_name='title', blank=True)),
                ('filename', models.FilePathField(path=settings.MEDIA_ROOT, unique=True, max_length=255, verbose_name='file name', recursive=True)),
            ],
            options={
                'permissions': (('can_listen_songs', 'Can listen songs'),),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='YouTubeDownloadTask',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('video_id', models.CharField(max_length=11, validators=[django.core.validators.RegexValidator(b'^[a-zA-Z0-9_-]{11}$')])),
                ('task_id', models.CharField(unique=True, max_length=50)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
