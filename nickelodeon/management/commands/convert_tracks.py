import os.path
import sys
import time
import re

from django.core.management.base import BaseCommand, CommandError

from nickelodeon.conf import settings
from nickelodeon.utils import convert_audio

try:
    from scandir import walk
except ImportError:
    from os import walk


MP3_FILE_EXT_RE = re.compile(r'(.+)\.mp3$', re.IGNORECASE)
AAC_FILE_EXT_RE = re.compile(r'(.+)\.aac$', re.IGNORECASE)
ROOT_DIRECTORY = settings.NICKELODEON_MEDIA_ROOT


class Command(BaseCommand):
    args = '[folder]'
    help = 'Scan the media folder and convert files found in aac or mp3'
    songs_to_convert = []
    t0 = t1 = last_flush = 0
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
                self.folder_root = os.path.join(
                    settings.NICKELODEON_MEDIA_ROOT,
                    folder)
        if not os.path.exists(self.folder_root):
            raise CommandError(
                u"Specified folder '{}' does not exist".format(
                    self.folder_root.decode(self.encoding)
                )
            )

    def handle(self, *args, **options):
        self.parse_args(args)
        self.t0 = self.last_flush = time.time()
        self.stdout.write(
            u'Scanning directory {} for unconverted songs'.format(
                self.folder_root.decode(self.encoding)
            )
        )
        self.t1 = self.last_flush = time.time()
        for filename in self.scan_directory():
            self.process_music_file(filename)
        nb_songs_to_convert = len(self.songs_to_convert)
        self.stdout.write(
            u'Discovered %d file(s) to convert'.format(nb_songs_to_convert)
        )
        if nb_songs_to_convert > 0:
            self.bulk_convert()
        self.stdout.write(
            u"Task completed in {} seconds".format(time.time()-self.t0)
        )

    def scan_directory(self):
        for root, dirs, files in walk(self.folder_root):
            for filename in files:
                if not isinstance(root, unicode):
                    root = root.decode(self.encoding)
                media_path = os.path.join(
                    root,
                    filename.decode(self.encoding)
                )
                yield media_path

    def process_music_file(self, media_path):
        if not MP3_FILE_EXT_RE.search(media_path) \
                and not AAC_FILE_EXT_RE.search(media_path):
            return
        if len(media_path)-len(settings.NICKELODEON_MEDIA_ROOT) > 255:
            self.stderr.write(u'Media path too long, '
                              u'255 characters maximum. {}'.format(media_path))
            return
        target_filename = media_path[:-4]
        ext = media_path[-4:].lower()
        target_ext = ".aac" if ext == ".mp3" else ".mp3"
        target = target_filename + target_ext
        if not os.path.exists(target):
            self.songs_to_convert.append({"src": media_path, "out": target})

    def print_conversion_status(self, progress):
        self.stdout.write(
            "{}%".format(min(100, int(progress*100))),
            ending='\r'
        )
        self.stdout.flush()

    def bulk_convert(self):
        for data in self.songs_to_convert:
            self.stdout.write(u"Converting {}".format(data['src']))
            kwargs = {"callback": self.print_conversion_status,
                      "output_file_{}".format(data['out'][-3:]): data['out']}
            convert_audio(data['src'], **kwargs)
