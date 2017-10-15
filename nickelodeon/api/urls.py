from django.conf.urls import url, include

from nickelodeon.api import views
from knox import views as knox_views

urlpatterns = [
    url(r'^auth/login/?$',
        view=views.LoginView.as_view(),
        name='knox_login'),
    url(r'^auth/logout/?$',
        view=knox_views.LogoutView.as_view(),
        name='knox_logout'),
    url(r'^auth/logoutall/?$',
        view=knox_views.LogoutAllView.as_view(),
        name='knox_logoutall'),
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