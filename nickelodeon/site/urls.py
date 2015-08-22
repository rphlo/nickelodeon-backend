from django.conf.urls import url, include
from django.views.generic import TemplateView
from django.contrib import admin


urlpatterns = [
    url(r'^(listen/?)?$',
        view=TemplateView.as_view(
            template_name="nickelodeon/music_player.html"),
        name='default_view'),
    url(r'^listen/(?P<pk>[a-zA-Z0-9_-]{11})/?$',
        view=TemplateView.as_view(
            template_name="nickelodeon/music_player.html"),
        name='song_view'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^api/', include('nickelodeon.api.urls')),
]
