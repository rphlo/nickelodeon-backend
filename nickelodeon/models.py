from __future__ import unicode_literals

import base64
import os
import random
import re
import struct
import sys

from django.conf import settings
from django.core.files.move import file_move_safe
from django.db import models
from django.utils.translation import ugettext as _

AVAILABLE_FORMATS = ('mp3', 'aac')


def random_key():
    rand_bytes = bytes(struct.pack('Q', random.getrandbits(64)))
    b64 = base64.b64encode(rand_bytes).decode('utf-8')
    b64 = b64[:11]
    b64 = b64.replace('+', '-')
    b64 = b64.replace('/', '_')
    return b64


class MP3Song(models.Model):
    id = models.CharField(default=random_key, max_length=12, primary_key=True)
    filename = models.CharField(verbose_name=_('file name'),
                                max_length=255,
                                unique=True,
                                db_index=True)

    @property
    def has_aac(self):
        file_path = self.get_file_format_path('aac') \
            .encode(sys.getfilesystemencoding())
        return os.path.exists(file_path)

    @property
    def has_mp3(self):
        file_path = self.get_file_format_path('mp3') \
            .encode(sys.getfilesystemencoding())
        return os.path.exists(file_path)

    @models.permalink
    def get_absolute_url(self):
        return "song_detail", (), {"pk": self.pk}

    @models.permalink
    def get_download_url(self):
        return "song_download", (), {"pk": self.pk}

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

    def move_file_from(self, orig):
        for ext, available in orig.available_formats.items():
            if available:
                src = orig.get_file_format_path(extension=ext, full=True)
                dst = self.get_file_format_path(extension=ext, full=True)
                dst_folder = os.path.dirname(dst)
                if not os.path.isdir(dst_folder):
                    os.makedirs(dst_folder)
                file_move_safe(src, dst)
                src_folder = os.path.dirname(src)
                while not os.listdir(src_folder):
                    os.rmdir(src_folder)
                    src_folder = os.path.dirname(src_folder)

    def remove_file(self):
        for ext in ['mp3', 'aac']:
            file_path = self.get_file_format_path(ext) \
                .encode(sys.getfilesystemencoding())
            if os.path.exists(file_path):
                os.remove(file_path)
