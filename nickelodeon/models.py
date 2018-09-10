from __future__ import unicode_literals

import os
import re
import sys

from django.conf import settings
from django.core.files.move import file_move_safe
from django.db import models
from django.urls import reverse
from django.utils.translation import ugettext as _

from nickelodeon.utils import clean_empty_folder, random_key


class MP3Song(models.Model):
    id = models.CharField(default=random_key, max_length=12, primary_key=True)
    filename = models.CharField(verbose_name=_('file name'),
                                max_length=255,
                                unique=True,
                                db_index=True)

    def has_extension(self, extension):
        file_path = self.get_file_format_path(extension) \
            .encode(sys.getfilesystemencoding())
        return os.path.exists(file_path)

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
            kwargs={'pk': self.pk, 'extension': 'mp3'}
        )

    @property
    def title(self):
        m = re.search(r'(?P<title>[^\/]+$)', self.filename)
        return m.group('title')

    @property
    def available_formats(self):
        return {'mp3': self.has_mp3, 'aac': self.has_aac}

    def get_file_format_path(self, extension='mp3', full=True):
        file_path = u"%s.%s" % (self.filename, extension)
        if full:
            file_path = os.path.join(settings.NICKELODEON_MUSIC_ROOT, file_path)
        return file_path

    def _move_file_ext_from(self, orig, ext):
        src = orig.get_file_format_path(extension=ext, full=True)
        dst = self.get_file_format_path(extension=ext, full=True)
        dst_folder = os.path.dirname(dst)
        if not os.path.isdir(dst_folder):
            os.makedirs(dst_folder)
        file_move_safe(src, dst)
        clean_empty_folder(os.path.dirname(src))

    def is_filename_available(self, filename):
        new_instance = MP3Song(filename=filename)
        for ext, available in self.available_formats.items():
            if available:
                dst = new_instance.get_file_format_path(
                    extension=ext,
                    full=True
                )
                if os.path.exists(dst):
                    return False
        return True

    def move_file_from(self, orig):
        for ext, available in orig.available_formats.items():
            if available:
                self._move_file_ext_from(orig, ext)

    def remove_file(self):
        for ext in ['mp3', 'aac']:
            file_path = self.get_file_format_path(ext) \
                .encode(sys.getfilesystemencoding())
            if os.path.exists(file_path):
                os.remove(file_path)
