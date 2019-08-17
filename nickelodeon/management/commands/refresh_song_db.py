import os.path
import sys
import time
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User

from nickelodeon.models import MP3Song
from nickelodeon.utils import get_s3_client, s3_object_exists


MP3_FILE_EXT_RE = re.compile(r'(.+)\.mp3$', re.IGNORECASE)


class Command(BaseCommand):
    args = '[folders]'
    help = 'Scan the media folder and update the database of music files'

    songs_to_find = set()
    songs_to_remove = set()
    songs_to_add = set()
    aac_list = []
    t0 = t1 = last_flush = songs_count = 0
    encoding = 'UTF-8'
    root = None
    owner = None

    def add_arguments(self, parser):
        parser.add_argument('folders', nargs='+', type=str)

    def handle_folder(self, root):
        self.root = root + '/'
        self.t0 = self.last_flush = time.time()
        self.songs_count = 0
        self.songs_to_add = []
        self.stdout.write(
            u'Scanning directory {} for music'.format(
                self.root
            )
        )
        self.t1 = self.last_flush = time.time()
        for filename in self.scan_directory():
            self.process_music_file(filename)
        self.t1 = self.last_flush = time.time()
        self.print_scan_status(True)
        current_song_qs = MP3Song.objects.all()
        prefix = self.root
        owner_username = self.root[:self.root.find('/')]
        self.owner = User.objects.get(username=owner_username)
        current_song_qs = current_song_qs.filter(
            owner=self.owner
        )
        prefix = prefix[len(owner_username)+1:]
        if prefix:
            current_song_qs = current_song_qs.filter(
                filename__startswith=prefix
            )
        current_songs = set(
            current_song_qs.values_list('filename', 'owner__username')
        )
        current_songs = set([
            s[1] + '/' + s[0] for s in current_songs
        ])
        self.songs_to_add = set(self.songs_to_add)
        self.songs_to_remove = [song for song in current_songs
                                if song not in self.songs_to_add]
        self.songs_to_add = [song for song in self.songs_to_add
                             if song not in current_songs]
        self.finalize()
        
    def handle(self, *args, **options):
        folders = options['folders']
        if not folders:
            folders = ['']
        for folder in folders:
            self.handle_folder(folder)
        
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
        s3 = get_s3_client()
        kwargs = {'Bucket': settings.S3_BUCKET, 'Prefix': self.root}
        while True:
            resp = s3.list_objects_v2(**kwargs)
            for obj in resp['Contents']:
                key = obj['Key']
                if key.endswith('.mp3'):
                    yield key
                if key.endswith('.aac'):
                    self.aac_list.append(key[:-4])
            try:
                kwargs['ContinuationToken'] = resp['NextContinuationToken']
            except KeyError:
                break

    def process_music_file(self, media_path):
        if not MP3_FILE_EXT_RE.search(media_path):
            return
        if len(media_path) > 255:
            self.stderr.write(
                u'Media path too long, '
                u'255 characters maximum. %s' % media_path
            )
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
                    round(time.time()-self.t1, 1)
                ),
                ending=''
            )
            self.stdout.flush()

    def has_aac(self, filename):
        return filename in self.aac_list

    def bulk_create(self):
        bulk = []
        self.aac_list = set(self.aac_list)
        for song_file in self.songs_to_add:
            bulk.append(MP3Song(
                filename=song_file[len(self.owner.username)+1:],
                aac=self.has_aac(song_file),
                owner=self.owner
            ))
        MP3Song.objects.bulk_create(bulk)

    def bulk_remove(self):
        files = []
        username_len = len(self.owner.username)+1
        for song_file in self.songs_to_remove:
            files.append(song_file[username_len:])
        MP3Song.objects.filter(
            owner_id=self.owner.id,
            filename__in=set(files)
        ).delete()