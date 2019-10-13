import os
import tempfile

from django.core.management.base import BaseCommand

from nickelodeon.models import MP3Song
from nickelodeon.utils import convert_audio, s3_object_url, s3_upload


class Command(BaseCommand):
    help = 'Create the missing aac files of the songs in the library'

    def handle(self, *args, **options):
        songs = MP3Song.objects.all()
        for song in songs:
            try:
                self.handle_song(song)
            except KeyboardInterrupt:
                aac_path = song.get_file_format_path('aac')
                break

    def handle_song(self, song):
        if not song.has_aac and song.has_mp3:
            mp3_path = song.get_file_format_path('mp3')
            aac_path = song.get_file_format_path('aac')
            mp3_url = s3_object_url(mp3_path)
            with tempfile.NamedTemporaryFile() as aac_file:
                aac_tmp_path = aac_file.name
            convert_audio(
                mp3_url,
                output_file_aac=aac_tmp_path,
            )
            s3_upload(aac_tmp_path, aac_path)
        if not song.aac:
            song.aac = True
            song.save()

    def print_conversion_progress(self, perc):
        self.stdout.write('\r{}%'.format(round(100*perc, 1)), ending='')
