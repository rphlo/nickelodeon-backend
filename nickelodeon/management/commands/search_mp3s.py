import os.path
import sys
import time
import re

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from common_base.core.models import safe_bulk_create
from common_base.utils.format import readable_duration

from nickelodeon.models import Song

try:
    from scandir import walk
except ImportError:
    from os import walk


MP3_FILE_EXT_RE = re.compile(r'(.+)\.(mp3)$', re.IGNORECASE)


class Command(BaseCommand):
    args = ''
    help = 'Scan the media folder and update the database of mp3 files'
    
    def scan_directory(self):
        for root, dirs, files in walk(os.path.join(settings.MEDIA_ROOT, 
                                                   'exthd', 'music')):
            for file in files:
                media_path = os.path.join(
                    root[len(settings.MEDIA_ROOT):], 
                    file.decode(sys.getfilesystemencoding())
                )
                yield media_path

    def process_mp3(self, media_path):
        if not MP3_FILE_EXT_RE.search(media_path):
            return
        if len(media_path) > 255:
            self.stderr(u'Media path too long, '
                        u'255 characters maximum. %s' % media_path)
            return
        if media_path in self.songs_to_find:
            self.songs_to_find.remove(media_path)
        else:
            media_dir, title = os.path.split(media_path[:-4])
            self.songs_added.append(
                Song(
                    filename=media_path, 
                    title=title
                )
            )
        self.songs_count += 1
        self.print_scan_status()
 
    def print_scan_status(self, force=False):
        if time.time() - self.last_flush > 1 or force:
            self.last_flush = time.time()
            self.stdout.write(
                u'\rScanned %d MP3s in %s' % (
                    self.songs_count, 
                    readable_duration(time.time()-self.t1)
                ), 
                ending=""
            )
            self.stdout.flush()
    
    def handle(self, *args, **options):
        self.t0 = self.last_flush = time.time()
        self.songs_count = 0
        self.songs_added = []
        self.encoding = sys.getfilesystemencoding()
        if not os.path.exists(os.path.join(settings.MEDIA_ROOT, 'exthd')):
            self.stderr.write(u"Drive not mounted.")
            return
        self.stdout.write(u'Loading cached files...')
        self.songs_to_find = set(Song.objects.all().values_list('filename', 
                                                                flat=True))
        self.stdout.write(u'Scanning music directory')
        self.t1 = self.last_flush = time.time()
        for file in self.scan_directory():
            self.process_mp3(file)
        self.print_scan_status(True)
        self.stdout.write(
            u'\nDiscovered %d new song(s), '
            u'Removing %d' % (len(self.songs_added), 
                              len(self.songs_to_find))
        )
        if len(self.songs_to_find) > 0:
            Song.objects.filter(filename__in=self.songs_to_find).delete()
        if len(self.songs_added) > 0:
            safe_bulk_create(self.songs_added)
        self.stdout.write(
            u"Task completed in %s" % readable_duration(time.time()-self.t0)
        )
