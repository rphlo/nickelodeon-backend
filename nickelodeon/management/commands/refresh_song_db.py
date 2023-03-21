import re
import time

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from nickelodeon.models import MP3Song, UserSettings
from nickelodeon.utils import get_s3_client

MP3_FILE_EXT_RE = re.compile(r"(.+)\.mp3$", re.IGNORECASE)
AAC_FILE_EXT_RE = re.compile(r"(.+)\.mp3$", re.IGNORECASE)


class Command(BaseCommand):
    args = "[folders]"
    help = "Scan the media folder and update the database of music files"

    songs_to_find = set()
    songs_to_remove = set()
    songs_to_add = set()
    aac_set = set()
    aac_list = []
    t0 = t1 = last_flush = songs_count = 0
    encoding = "UTF-8"
    root = None
    owner = None

    def add_arguments(self, parser):
        parser.add_argument("folders", nargs="*", type=str)

    def handle_folder(self, root):
        self.root = root + "/"
        self.t0 = self.last_flush = time.time()
        
        self.songs_count = 0
        self.songs = []
        self.songs_with_aac = []
        
        self.stdout.write("Scanning directory {} for music".format(self.root))
        self.t1 = self.last_flush = time.time()

        for filename in self.scan_directory():
            self.process_music_file(filename)

        self.t1 = self.last_flush = time.time()
        self.print_scan_status(True)

        prefix = self.root
        root_folder = self.root[:self.root.find("/")]
        try:
            self.owner = UserSettings.objects.get_or_create(
                storage_prefix=root_folder
            )[0].user
        except UserSettings.DoesNotExist:
            self.owner = User.objects.get(username=root_folder)

        current_songs_qs = MP3Song.objects.filter(owner=self.owner)
        prefix = prefix[len(root_folder) + 1 :]
        if prefix:
            current_songs_qs = current_songs_qs.filter(filename__startswith=prefix)

        current_songs = set([f"{self.owner.settings.storage_prefix}/{s.filename}" for s in current_songs_qs])
        current_songs_with_aac_tag = set([f"{self.owner.settings.storage_prefix}/{s.filename}" for s in current_songs_qs.filter(aac=True)])
        current_songs_without_aac_tag = set([f"{self.owner.settings.storage_prefix}/{s.filename}" for s in current_songs_qs.filter(aac=False)])
        
        self.aac_set = set(self.aac_list)
        
        self.songs = set(self.songs)
        self.songs_to_remove = [
            song for song in current_songs if song not in self.songs
        ]
        self.songs_to_add = [
            song for song in self.songs if song not in current_songs
        ]
        self.songs_to_remove_aac_tag = [
            song for song in current_songs_with_aac if song not in self.aac_set
        ]
        self.songs_to_add_aac_tag = [
            song for song in self.aac_set if song in current_songs_without_aac_tag
        ]
        self.finalize()

    def handle(self, *args, **options):
        folders = options["folders"]
        if not folders:
            folders = [u.settings.storage_prefix for u in User.objects.all()]
        for folder in folders:
            self.handle_folder(folder)

    def finalize(self):
        nb_songs_to_add = len(self.songs_to_add)
        nb_songs_to_remove = len(self.songs_to_remove)
        nb_song_to_add_aac = len(self.song_to_add_aac_tag)
        nb_song_to_remove_aac = len(self.song_to_remove_aac_tag)
        self.stdout.write("\nDiscovered {} new file(s)".format(nb_songs_to_add))
        self.stdout.write("Removing {} file(s)".format(nb_songs_to_remove))
        self.stdout.write("Removing AAC Tag to {} file(s)".format(nb_song_to_remove_aac))
        self.stdout.write("Adding AAC Tag to {} file(s)".format(nb_song_to_add_aac))
        if nb_songs_to_add > 0:
            self.bulk_create()
        if nb_songs_to_remove > 0:
            self.bulk_remove()
        self.bulk_aac_update()
        self.stdout.write(
            "Task completed in {} seconds".format(round(time.time() - self.t0, 1))
        )

    def scan_directory(self):
        s3 = get_s3_client()
        # Should use v2 but wasabi fails to list all files with it
        # paginator = s3.get_paginator('list_objects_v2')
        paginator = s3.get_paginator("list_objects")
        kwargs = {
            "Bucket": settings.S3_BUCKET,
            "Prefix": self.root,
        }
        for page in paginator.paginate(**kwargs):
            try:
                contents = page["Contents"]
            except KeyError:
                break

            for obj in contents:
                key = obj["Key"]
                if key.endswith(".mp3"):
                    yield key
                if key.endswith(".aac"):
                    self.aac_list.append(key[:-4])

    def process_music_file(self, media_path):
        if not MP3_FILE_EXT_RE.search(media_path):
            if AAC_FILE_EXT_RE.search(media_path):
                self.songs_with_aac.append(media_path[:-4])
            return
        if len(media_path) > 255:
            self.stderr.write(
                "Media path too long, " "255 characters maximum. %s" % media_path
            )
            return
        self.songs.append(media_path[:-4])
        self.songs_count += 1
        self.print_scan_status()

    def print_scan_status(self, force=False):
        if time.time() - self.last_flush > 1 or force:
            self.last_flush = time.time()
            self.stdout.write(
                "\rScanned {} music file(s) in {} seconds".format(
                    self.songs_count, round(time.time() - self.t1, 1)
                ),
                ending="",
            )
            self.stdout.flush()

    def has_aac(self, filename):
        return filename in self.aac_set

    def bulk_create(self):
        bulk = []
        for song_file in self.songs_to_add:
            bulk.append(
                MP3Song(
                    filename=song_file[len(self.owner.settings.storage_prefix) + 1 :],
                    aac=self.has_aac(song_file),
                    owner=self.owner,
                )
            )
        MP3Song.objects.bulk_create(bulk)

    def bulk_remove(self):
        files = []
        root_folder_len = len(self.owner.settings.storage_prefix) + 1
        for song_file in self.songs_to_remove:
            files.append(song_file[root_folder_len:])
        MP3Song.objects.filter(owner_id=self.owner.id, filename__in=set(files)).delete()
    
    def bulk_aac_update(self):
        root_folder_len = len(self.owner.settings.storage_prefix) + 1
        files = []
        for song_file in self.songs_to_add_aac_tag:
            files.append(song_file[root_folder_len:])
        MP3Song.objects.filter(owner_id=self.owner.id, filename__in=set(files)).update(aac=True)
        files = []
        for song_file in self.songs_to_remove_aac_tag:
            files.append(song_file[root_folder_len:])
        MP3Song.objects.filter(owner_id=self.owner.id, filename__in=set(files)).update(aac=False)
