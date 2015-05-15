import os.path
import sys
import time
import re

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from common_base.core.models import safe_bulk_create
from common_base.utils.format import readable_duration
from common_base.utils.strings import pluralize

from nickelodeon.models import Song

try:
    from scandir import walk
except ImportError:
    from os import walk


MP3_FILE_EXT_RE = re.compile(r'(.+)\.mp3$', re.IGNORECASE)
AAC_FILE_EXT_RE = re.compile(r'(.+)\.aac$', re.IGNORECASE)
ROOT_DIRECTORY = os.path.join(settings.MEDIA_ROOT, 'exthd', 'music')


class Command(BaseCommand):
    args = '[folder]'
    help = 'Scan the media folder and update the database of music files'

    songs_to_find = set()
    songs_to_remove = set()
    songs_to_add = set()
    t0 = t1 = last_flush = songs_count = 0
    encoding = 'UTF-8'
    folder_root = ROOT_DIRECTORY

    def parse_args(self, args):
        self.encoding = sys.getfilesystemencoding()
        if len(args) > 1:
            raise CommandError('Too many arguments. See usage.')
        elif len(args) == 1:
            folder = args[0]
            if folder[0] == '/':
                if folder.startswith(ROOT_DIRECTORY):
                    self.folder_root = folder
                else:
                    raise CommandError('Absolute path should be '
                                       'within Media root.')
            else:
                self.folder_root = os.path.join(settings.MEDIA_ROOT, folder)
        if not os.path.exists(self.folder_root):
            raise CommandError(
                u"Specified folder '{}' does not exist".format(
                    self.folder_root.decode(self.encoding)
                )
            )

    def handle(self, *args, **options):
        self.parse_args(args)
        self.t0 = self.last_flush = time.time()
        self.songs_count = 0
        self.songs_to_add = set()
        self.stdout.write(u'Loading cached files...')
        existing_songs = Song.objects.filter(
            filename__startswith=self.folder_root[len(settings.MEDIA_ROOT):]
        )
        self.songs_to_find = set(existing_songs.values_list('filename',
                                                            flat=True))
        self.songs_to_remove = self.songs_to_find.copy()
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
            u'\nDiscovered %d %s' % (
                nb_songs_to_add,
                pluralize('file', nb_songs_to_add)
            )
        )
        nb_songs_to_remove = len(self.songs_to_remove)
        if nb_songs_to_remove > 0:
            self.stdout.write(
                u'Could not find %d %s' % (
                    nb_songs_to_remove,
                    pluralize('file', nb_songs_to_remove)
                )
            )
            Song.objects.filter(filename__in=self.songs_to_remove).delete()
        if len(self.songs_to_add) > 0:
            self.bulk_create()
        self.stdout.write(
            u"Task completed in %s" % readable_duration(time.time()-self.t0)
        )

    def scan_directory(self):
        for root, dirs, files in walk(self.folder_root):
            for filename in files:
                if not isinstance(root, unicode):
                    root = root.decode(self.encoding)
                media_path = os.path.join(
                    root[len(settings.MEDIA_ROOT):],
                    filename.decode(self.encoding)
                )
                yield media_path

    def process_music_file(self, media_path):
        if not MP3_FILE_EXT_RE.search(media_path) \
                and not AAC_FILE_EXT_RE.search(media_path):
            return
        if len(media_path) > 255:
            self.stderr(u'Media path too long, '
                        u'255 characters maximum. %s' % media_path)
            return
        new_song = media_path[:-4]
        if new_song in self.songs_to_find:
            if new_song in self.songs_to_remove:
                self.songs_to_remove.remove(new_song)
            else:
                return
        else:
            if new_song in self.songs_to_add:
                return
            self.songs_to_add.add(new_song)
        self.songs_count += 1
        self.print_scan_status()

    def print_scan_status(self, force=False):
        if time.time() - self.last_flush > 1 or force:
            self.last_flush = time.time()
            self.stdout.write(
                u'\rScanned %d music %s in %s' % (
                    self.songs_count,
                    pluralize('file', self.songs_count),
                    readable_duration(time.time()-self.t1)
                ),
                ending=""
            )
            self.stdout.flush()

    def bulk_create(self):
        bulk = []
        for song_file in self.songs_to_add:
            media_dir, title = os.path.split(song_file)
            bulk.append(Song(
                title=title,
                filename=song_file
            ))
        safe_bulk_create(bulk)
