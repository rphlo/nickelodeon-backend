from django.core.management.base import BaseCommand

from nickelodeon.models import MP3Song
from nickelodeon.utils import convert_audio


class Command(BaseCommand):
    help = 'Create the missing aac files of the songs in the library'

    def handle(self, *args, **options):
        songs = MP3Song.objects.all()
        for song in songs:
            self.handle_song(song)

    def handle_song(self, song):
        if not song.has_aac and song.has_mp3:
            mp3_path = song.get_file_format_path('mp3')
            aac_path = song.get_file_format_path('aac')
            self.stdout.write('Converting {}'.format(mp3_path))
            convert_audio(
                mp3_path,
                output_file_aac=aac_path,
                callback=self.print_conversion_progress
            )
            song.aac = True
            song.save()
            self.stdout.write('Done')

    def print_conversion_progress(self, perc):
        self.stdout('\r{}%'.format(perc), ending='')
