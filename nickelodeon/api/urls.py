from django.conf.urls import url

from nickelodeon.api import views



urlpatterns = [
    url(r'^songs/?$',
        view=views.TextSearchApiView.as_view(),
        name='song_list'),
    url(r'^songs/random/?$',
        view=views.RandomSongView.as_view(),
        name='song_detail'),
    url(r'^songs/(?P<pk>[a-zA-Z0-9_-]{11})/?$',
        view=views.SongView.as_view(),
        name='song_detail'),
    url(r'^songs/dl/(?P<pk>[a-zA-Z0-9_-]{11})'
        r'(\.(?P<extension>(mp3|aac)))?$',
        view=views.download_song,
        name='song_download'),
]