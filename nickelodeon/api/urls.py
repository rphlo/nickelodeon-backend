from django.conf.urls import url

from rest_framework.authtoken import views as token_views

from nickelodeon.api import views


urlpatterns = [
    url(r'^auth_token/', token_views.obtain_auth_token),
    url(r'^songs/?$',
        view=views.TextSearchApiView.as_view(),
        name='song_list'),
    url(r'^songs/random/?$',
        view=views.RandomSongView.as_view(),
        name='song_random'),
    url(r'^songs/(?P<pk>[a-zA-Z0-9_-]{11})/?$',
        view=views.SongView.as_view(),
        name='song_detail'),
    url(r'^songs/dl/(?P<pk>[a-zA-Z0-9_-]{11})'
        r'(\.(?P<extension>(mp3|aac)))?$',
        view=views.download_song,
        name='song_download'),
    url(r'^youtube-dl/(?P<video_id>[a-zA-Z0-9_-]{11})/?$',
        view=views.youtube_grab,
        name='youtube_grab')
]