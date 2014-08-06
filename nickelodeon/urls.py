from django.conf.urls import patterns, url
from django.views.generic import TemplateView
from . import views


urlpatterns = patterns('',
    url(r'^jukebox$',
        view=TemplateView.as_view(template_name="nickelodeon/music_player.html"),
        name='music_player'),
    url(r'^api/v1/songs$',
        view=views.TextSearchApiView.as_view(),
        name='song_list'),
    url(r'^api/v1/song/(?P<pk>[a-zA-Z0-9]{22})/?$',
        view=views.SongView.as_view(),
        name='song_detail'),
)
