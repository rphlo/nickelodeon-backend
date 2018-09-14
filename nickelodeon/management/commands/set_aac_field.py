from django.core.management.base import BaseCommand

from nickelodeon.models import MP3Song




class Command(BaseCommand):
    help = 'Set the aac field on all MP3Songs'
    counter = 0
    has_aac_ids = set()
    has_not_aac_ids = set()

    def handle(self, *args, **options):
        songs = MP3Song.objects.all()
        self.counter = 0
        for song in songs:
            self.handle_song(song)

        MP3Song.objects.filter(id__in=self.has_aac_ids).update(aac=True)
        MP3Song.objects.filter(id__in=self.has_not_aac_ids).update(aac=False)

        self.stdout.write('Updated %d songs' % self.counter)

    def handle_song(self, song):
        if song.aac != song.has_aac:
            if song.has_aac:
                self.has_aac_ids.add(song.id)
            else:
                self.has_not_aac_ids.add(song.id)
            self.counter += 1
