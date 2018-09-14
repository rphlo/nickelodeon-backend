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
                    self.folder_root
                )
            )

    def handle(self, *args, **options):
        self.parse_args(args, options)
        self.t0 = self.last_flush = time.time()
        self.songs_count = 0
        self.songs_to_add = []
        self.stdout.write(
            u'Scanning directory {} for music'.format(
                self.folder_root
            )
        )
        self.t1 = self.last_flush = time.time()
        for filename in self.scan_directory():
            self.process_music_file(filename)
        self.print_scan_status(True)
        self.songs_to_add = set(self.songs_to_add)
        current_songs = set(MP3Song.objects.all().values_list('filename',
                                                              flat=True))
        self.songs_to_remove = [song for song in current_songs
                                if song not in self.songs_to_add]
        self.songs_to_add = [song for song in self.songs_to_add
                             if song not in current_songs]
        self.finalize()

    def finalize(self):
        nb_songs_to_add = len(self.songs_to_add)
        nb_songs_to_remove = len(self.songs_to_remove)
        self.stdout.write(
            u'\nDiscovered {} new file(s)'.format(nb_songs_to_add)
        )
        self.stdout.write(
            u'Removing {} file(s)'.format(nb_songs_to_remove)
        )
        if nb_songs_to_add > 0:
            self.bulk_create()
        if nb_songs_to_remove > 0:
            self.bulk_remove()
        self.stdout.write(
            u'Task completed in {} seconds'.format(
                round(time.time()-self.t0, 1)
            )
        )

    def scan_directory(self):
        for root, dirs, files in walk(self.folder_root):
            for filename in files:
                media_path = os.path.join(
                    root[len(self.folder_root):],
                    filename
                )
                yield media_path

    def process_music_file(self, media_path):
        if not MP3_FILE_EXT_RE.search(media_path):
            return
        if len(media_path) > 255:
            self.stderr.write(u'Media path too long, '
                              u'255 characters maximum. %s' % media_path)
            return
        new_song = media_path[:-4]
        if new_song.startswith('/'):
            new_song = new_song[1:]
        self.songs_to_add.append(new_song)
        self.songs_count += 1
        self.print_scan_status()

    def print_scan_status(self, force=False):
        if time.time() - self.last_flush > 1 or force:
            self.last_flush = time.time()
            self.stdout.write(
                u'\rScanned {} music file(s) in {} seconds'.format(
                    self.songs_count,
                    round(time.time()-self.t1, 1)
                ),
                ending=''
            )
            self.stdout.flush()

    def has_aac(self, filename):
        return os.path.exists(os.path.join(self.folder_root, filename+'.aac'))

    def bulk_create(self):
        bulk = []
        for song_file in self.songs_to_add:
            bulk.append(MP3Song(
                filename=song_file,
                aac=self.has_aac(song_file)
            ))
        MP3Song.objects.bulk_create(bulk)

    def bulk_remove(self):
        MP3Song.objects.filter(filename__in=self.songs_to_remove).delete()
