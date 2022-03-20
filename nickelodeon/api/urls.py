from django.urls import re_path
from knox import views as knox_views

from nickelodeon.api import views

urlpatterns = [
    re_path(r"^$", views.api_root, name="api_root"),
    re_path(r"^login/?$", view=views.LoginView.as_view(), name="knox_login"),
    re_path(r"^logout/?$", view=knox_views.LogoutView.as_view(), name="knox_logout"),
    re_path(
        r"^logoutall/?$", view=knox_views.LogoutAllView.as_view(), name="knox_logoutall"
    ),
    re_path(
        r"^account/change_password/?$",
        view=views.PasswordChangeView.as_view(),
        name="account_change_password",
    ),
    re_path(r"^songs/?$", view=views.TextSearchApiView.as_view(), name="song_list"),
    re_path(
        r"^songs/random/?$", view=views.RandomSongView.as_view(), name="song_random"
    ),
    re_path(
        r"^songs/(?P<pk>[a-zA-Z0-9_-]{11})/?$",
        view=views.SongView.as_view(),
        name="song_detail",
    ),
    re_path(
        r"^songs/(?P<pk>[a-zA-Z0-9_-]{11})/file.jpg$",
        view=views.download_cover,
        name="song_cover",
    ),
    re_path(
        r"^songs/(?P<pk>[a-zA-Z0-9_-]{11})/file$",
        view=views.download_song,
        name="song_download",
    ),
    re_path(
        r"^songs/(?P<pk>[a-zA-Z0-9_-]{11})/file\.(?P<extension>(mp3|aac))$",
        view=views.download_song,
        name="song_download",
    ),
    re_path(r"^youtube-dl/?$", view=views.youtube_grab, name="youtube_grab"),
    re_path(r"^mp3-upload/?", views.ResumableUploadView.as_view(), name="mp3-upload"),
    re_path(r"^tasks/?$", view=views.tasks_list, name="task_status"),
    re_path(
        r"^tasks/(?P<task_id>[a-f0-9-]{36})/?$",
        view=views.task_status,
        name="task_status",
    ),
]
