from django.db import models
from django.utils.translation import ugettext as _
from common_base.core.models import UuidModel
from django.conf import settings
import os.path

class Song(UuidModel):
    artist = models.CharField(_('artist'),
                              max_length=255, blank=True)
    title = models.CharField(_('title'),
                             max_length=255, blank=True)
    filename = models.FilePathField(path=settings.MEDIA_ROOT,
                                    match='.*\.mp3$', recursive=True,
                                    allow_files=True, allow_folders=False,
                                    verbose_name=_('file name'),
                                    max_length=255, unique=True)

    def __unicode__(self):
        if self.artist:
            return u"%s - %s" % (self.artist, self.title)
        return u"%s" % self.title

    def get_file_format_path(self, extension, full=True):
        file_path = "%s.%s" % (self.filename[:-4], extension)
        if full:
            file_path = os.path.join(settings.MEDIA_ROOT, file_path[1:])
        return file_path

    def file_format_available(self, extension):
        if os.path.exists(self.get_file_format_path(extension)):
            return True
        return False

    @property
    def available_formats(self):
        result = {}
        for ext in ('mp3', 'aac'):
            result[ext] = self.file_format_available(ext)
        return result

    @models.permalink
    def get_absolute_url(self, force_mp3=False):
        return ("song_detail", (), {"pk":self.pk})
