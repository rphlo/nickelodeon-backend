import os.path
import sys
import time
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from nickelodeon.models import MP3Song

try:
    from scandir import walk
except ImportError:
    from os import walk


MP3_FILE_EXT_RE = re.compile(r'(.+)\.mp3$', re.IGNORECASE)


class Command(BaseCommand):
    args = '[folder]'
    help = 'Scan the media folder and update the database of music files'

    songs_to_find = set()
    songs_to_remove = set()
    songs_to_add = set()
    t0 = t1 = last_flush = songs_count = 0
    encoding = 'UTF-8'
    folder_root = None

    def parse_args(self, args, options):
        self.encoding = sys.getfilesystemencoding()
        self.folder_root = settings.NICKELODEON_MUSIC_ROOT
        if not os.path.exists(self.folder_root):
            raise CommandError(
                u'Specified folder "{}" does not exist'.format(
                    self.folder_root.decode(self.encoding)
                )
            )

    def handle(self, *args, **options):
        self.parse_args(args, options)
        self.t0 = self.last_flush = time.time()
        self.songs_count = 0
        self.songs_to_add = []
        self.stdout.write(
            u'Scanning directory {} for music'.format(
                self.folder_root.decode(self.encoding)
            )
        )
        self.t1 = self.last_flush = time.time()
        for filename in self.scan_directory():
            self.process_music_file(filename)
        self.print_scan_status(True)
        nb_songs_to_add = len(self.songs_to_add)
        self.stdout.write(
            u'\nDiscovered {} file(s)'.format(nb_songs_to_add)
        )
        MP3Song.objects.all().delete()
        if len(self.songs_to_add) > 0:
            self.bulk_create()
        self.stdout.write(
            u'Task completed in {} seconds'.format(time.time()-self.t0)
        )

    def scan_directory(self):
        for root, dirs, files in walk(self.folder_root):
            for filename in files:
                if not isinstance(root, unicode):
                    root = root.decode(self.encoding)
                media_path = os.path.join(
                    root[len(self.folder_root):],
                    filename.decode(self.encoding)
                )
                yield media_path

    def process_music_file(self, media_path):
        if not MP3_FILE_EXT_RE.search(media_path):
            return
        if len(media_path) > 255:
            self.stderr(u'Media path too long, '
                        u'255 characters maximum. %s' % media_path)
            return
        new_song = media_path[:-4]
        self.songs_to_add.append(new_song)
        self.songs_count += 1
        self.print_scan_status()

    def print_scan_status(self, force=False):
        if time.time() - self.last_flush > 1 or force:
            self.last_flush = time.time()
            self.stdout.write(
                u'\rScanned {} music file(s) in {} seconds'.format(
                    self.songs_count,
                    time.time()-self.t1
                ),
                ending=''
            )
            self.stdout.flush()

    def bulk_create(self):
        bulk = []
        for song_file in self.songs_to_add:
            bulk.append(MP3Song(
                filename=song_file
            ))
        MP3Song.objects.bulk_create(bulk)
