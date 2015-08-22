import sys
import os.path
import random
import struct

from django.db import models
from django.utils.translation import ugettext as _
from django.conf import settings
from django.core.files.move import file_move_safe
from django.core.validators import RegexValidator


AVAILABLE_FORMATS = ('mp3', 'aac')


def random_key():
    b64 = bytes(struct.pack('L', random.getrandbits(64))).encode('base64')
    b64 = b64[:11]
    b64 = b64.replace('+', '-')
    b64 = b64.replace('/', '_')
    return b64


class Song(models.Model):
    id = models.CharField(default=random_key, max_length=12, primary_key=True)
    artist = models.CharField(_('artist'),
                              max_length=255, blank=True)
    title = models.CharField(_('title'),
                             max_length=255, blank=True)
    filename = models.FilePathField(path=settings.MEDIA_ROOT,
                                    recursive=True, allow_files=True,
                                    allow_folders=False,
                                    verbose_name=_('file name'),
                                    max_length=255,
                                    unique=True,
                                    db_index=True)

    def __unicode__(self):
        if self.artist:
            return u"%s - %s" % (self.artist, self.title)
        return u"%s" % self.title

    def get_file_format_path(self, extension, full=True):
        file_path = u"%s.%s" % (self.filename, extension)
        if full:
            file_path = os.path.join(settings.NICKELODEON_MEDIA_ROOT,
                                     file_path)
        return file_path

    def file_format_available(self, extension):
        file_path = self.get_file_format_path(extension)
        if os.path.exists(file_path.encode(sys.getfilesystemencoding())):
            return True
        return False

    @property
    def available_formats(self):
        result = {}
        for ext in AVAILABLE_FORMATS:
            result[ext] = self.file_format_available(ext)
        return result

    @models.permalink
    def get_absolute_url(self):
        return "song_detail", (), {"pk": self.pk}

    @models.permalink
    def get_download_url(self):
        return "song_download", (), {"pk": self.pk}

    def move_file_from(self, orig):
        for ext, available in orig.available_formats.iteritems():
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
        for ext in AVAILABLE_FORMATS:
            file_path = self.get_file_format_path(ext)\
                            .encode(sys.getfilesystemencoding())
            if os.path.exists(file_path):
                os.remove(file_path)

    class Meta:
        permissions = (("can_listen_songs", _("Can listen songs")),)


class YouTubeDownloadTask(models.Model):
    video_id = models.CharField(max_length=11,
                                validators=[
                                    RegexValidator('^[a-zA-Z0-9_-]{11}$'),
                                ])
    task_id = models.CharField(max_length=50, unique=True)

    @models.permalink
    def get_task_url(self):
        return 'task_status', (), {'task_id': self.task_id}

    def save(self, *args, **kwargs):
        from nickelodeon.tasks import fetch_youtube_video
        if not self.task_id:
            task = fetch_youtube_video.s(self.video_id).delay()
            self.task_id = str(task.task_id)
        super(YouTubeDownloadTask, self).save(*args, **kwargs)
