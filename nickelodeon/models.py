from __future__ import unicode_literals

import os
import re

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from django.contrib.auth.models import User

from nickelodeon.utils import (
    random_key,
    s3_move_object,
    s3_object_exists,
    s3_object_delete,
)


class UserSettings(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )
    storage_prefix = models.CharField(max_length=32, default=random_key, unique=True)

    class Meta:
        verbose_name = 'user settings'
        verbose_name_plural = 'user settings'


User.settings = property(lambda u: UserSettings.objects.get_or_create(user=u, defaults={'storage_prefix': u.username})[0])


@receiver(post_save, sender=User, dispatch_uid="create_user_settings")
def create_settings(sender, instance, created, **kwargs):
    if created and not UserSettings.objects.filter(user=instance).exists():
        UserSettings.objects.create(user=instance, storage_prefix=f'{instance.username}-{random_key()}')


class MP3Song(models.Model):
    id = models.CharField(default=random_key, max_length=12, primary_key=True)
    filename = models.CharField(
        verbose_name='file name',
        max_length=255,
    )
    aac = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    def has_extension(self, extension):
        file_path = self.get_file_format_path(extension) \
            .encode('utf-8')
        return s3_object_exists(file_path)

    @property
    def has_aac(self):
        return self.has_extension('aac')

    @property
    def has_mp3(self):
        return self.has_extension('mp3')

    def get_absolute_url(self):
        return reverse("song_detail", kwargs={"pk": self.pk})

    def get_download_url(self):
        return reverse(
            'song_download',
            kwargs={'pk': self.pk}
        )

    @property
    def owner_username(self):
        return self.owner.username
    @property
    def title(self):
        m = re.search(r'(?P<title>[^\/]+$)', self.filename)
        return m.group('title')

    @property
    def available_formats(self):
        return {'mp3': self.has_mp3, 'aac': self.has_aac}

    def get_file_format_path(self, extension='mp3'):
        file_path = u"{}/{}.{}".format(
            self.owner.settings.storage_prefix,
            self.filename,
            extension
        )
        return os.path.normpath(file_path)

    def _move_file_ext_from(self, orig, ext):
        src = orig.get_file_format_path(extension=ext)
        dst = self.get_file_format_path(extension=ext)
        s3_move_object(src, dst)

    def is_filename_available(self, filename, owner):
        new_instance = MP3Song(filename=filename, owner=owner)
        for ext, available in self.available_formats.items():
            if available:
                dst = new_instance.get_file_format_path(
                    extension=ext
                )
                if s3_object_exists(dst):
                    return False
        return True

    def move_file_from(self, orig):
        for ext, available in orig.available_formats.items():
            if available:
                self._move_file_ext_from(orig, ext)

    def remove_file(self):
        for ext in ['mp3', 'aac']:
            file_path = self.get_file_format_path(ext) \
                .encode('utf-8')
            if s3_object_exists(file_path):
                s3_object_delete(file_path)

    class Meta:
        unique_together = ['owner', 'filename']

