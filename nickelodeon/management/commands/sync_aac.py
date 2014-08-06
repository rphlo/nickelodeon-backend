import os.path
import sys
import time
import re

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from common_base.core.models import safe_bulk_create

from nickelodeon.models import Song

try:
    from scandir import walk
except ImportError:
    from os import walk


MP3_FILE_EXT_RE = re.compile(r'(.+)\.mp3$', re.IGNORECASE)
AAC_FILE_EXT_RE = re.compile(r'(.+)\.aac$', re.IGNORECASE)


class Command(BaseCommand):
    args = ''
    help = 'Maintain the AAC compressed version of the MP3s'

    t0 = t1 = None
    aac_count = 0
    mp3_count = 0
    missing_aac = []
    extra_aac = []
    encoding = sys.getfilesystemencoding()
    last_flush = None

    def scan_directory(self):
        for root, dirs, files in walk(os.path.join(settings.MEDIA_ROOT, 
                                                   'exthd', 'music')):
            for filename in files:
                media_path = os.path.join(
                    root[len(settings.MEDIA_ROOT):], 
                    filename.decode(sys.getfilesystemencoding())
                )
                yield media_path

    def process_file(self, path):
        if MP3_FILE_EXT_RE.search(path):
            return self.process_mp3(path)
        elif AAC_FILE_EXT_RE.search(path):
            return self.process_aac(path)
        return

    def process_mp3(self, media_path):
        aac_path = re.sub(r'\.mp3$', '.aac', media_path)
        if not os.path.exists(os.path.join(settings.MEDIA_ROOT, aac_path[1:])):
            self.missing_aac.append(media_path)
        self.mp3_count += 1
        self.print_scan_status()

    def process_aac(self, media_path):
        mp3_path = re.sub(r'\.aac$', '.mp3', media_path)
        if not os.path.exists(os.path.join(settings.MEDIA_ROOT, mp3_path[1:])):
            self.extra_aac.append(media_path)
        self.aac_count += 1
        self.print_scan_status()
 
    def print_scan_status(self, force=False):
        if time.time() - self.last_flush > 1 or force:
            self.last_flush = time.time()
            self.stdout.write(
                '\rScanned %d MP3, %d AAC tracks in %d seconds' % (
                    self.mp3_count, self.aac_count,
                    int(time.time()-self.t1)
                ), 
                ending=""
            )
            self.stdout.flush()

    def handle(self, *args, **options):
        self.t0 = self.last_flush = time.time()
        if not os.path.exists(os.path.join(settings.MEDIA_ROOT, 'exthd',
                                           'music')):
            self.stderr.write(u"Drive not mounted.")
            return
        self.stdout.write(u'Scanning music directory')
        self.t1 = self.last_flush = time.time()
        for path in self.scan_directory():
            self.process_file(path)
        self.print_scan_status(True)
        self.stdout.write(
            u'\nDiscovered %d MP3 without AAC, '
            u'Removing %d AAC' % (len(self.missing_aac),
                                  len(self.extra_aac))
        )
        self.stdout.write(u"Missing AAC\n"
                          u"%r\n\n"
                          u"Extra AAC\n%r" % (self.missing_aac,
                                              self.extra_aac))
        self.stdout.write(
            "Task completed in %d seconds" % int(time.time()-self.t0)
        )
