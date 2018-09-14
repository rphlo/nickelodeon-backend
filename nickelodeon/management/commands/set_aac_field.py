from django.core.management.base import BaseCommand

from nickelodeon.models import MP3Song




class Command(BaseCommand):
    help = 'Create the missing aac files of the songs in the library'
    counter = 0

    def handle(self, *args, **options):
        songs = MP3Song.objects.all()
        self.counter = 0
        for song in songs:
            self.handle_song(song)
        self.stdout.write('Updated %d songs' % self.counter)

    def handle_song(self, song):
        if song.aac != song.has_aac:
            song.aac = song.has_aac
            song.save()
            self.counter += 1
