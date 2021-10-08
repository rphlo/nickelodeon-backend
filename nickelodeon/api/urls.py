from django.conf.urls import url
from django.contrib.admin.views.decorators import staff_member_required

from nickelodeon.api import views
from knox import views as knox_views

urlpatterns = [
    url(r'^$',
        views.api_root,
        name='api_root'),
    url(r'^login/?$',
        view=views.LoginView.as_view(),
        name='knox_login'),
    url(r'^logout/?$',
        view=knox_views.LogoutView.as_view(),
        name='knox_logout'),
    url(r'^logoutall/?$',
        view=knox_views.LogoutAllView.as_view(),
        name='knox_logoutall'),
    url(r'^account/change_password/?$',
        view=views.PasswordChangeView.as_view(),
        name='account_change_password'),
    url(r'^songs/?$',
        view=views.TextSearchApiView.as_view(),
        name='song_list'),
    url(r'^songs/random/?$',
        view=views.RandomSongView.as_view(),
        name='song_random'),
    url(r'^songs/(?P<pk>[a-zA-Z0-9_-]{11})/?$',
        view=views.SongView.as_view(),
        name='song_detail'),
    url(r'^songs/(?P<pk>[a-zA-Z0-9_-]{11})/file.jpg$',
        view=views.download_cover,
        name='song_cover'),
    url(r'^songs/(?P<pk>[a-zA-Z0-9_-]{11})/file$',
        view=views.download_song,
        name='song_download'),
    url(r'^songs/(?P<pk>[a-zA-Z0-9_-]{11})/file\.(?P<extension>(mp3|aac))$',
        view=views.download_song,
        name='song_download'),
    url(r'^youtube-dl/?$',
        view=views.youtube_grab,
        name='youtube_grab'),
    url(r'^mp3-upload/?',
        views.ResumableUploadView.as_view(),
        name='mp3-upload'),
    url(r'^tasks/?$',
        view=views.tasks_list,
        name='task_status'),
    url(r'^tasks/(?P<task_id>[a-f0-9-]{36})/?$',
        view=views.task_status,
        name='task_status'),
]
