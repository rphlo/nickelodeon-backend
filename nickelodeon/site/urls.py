from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import login, logout
from django.views.generic import TemplateView


urlpatterns = [
    url(r'^/?$',
        view=TemplateView.as_view(
            template_name="nickelodeon/music_home.html"),
        name='default_view'),
    url(r'^listen/(?P<pk>[a-zA-Z0-9_-]{11})?(\.html)?$',
        view=login_required(TemplateView.as_view(
                template_name="nickelodeon/music_player.html")),
        name='song_view'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^api/', include('nickelodeon.api.urls')),
    url(r'^login/$', login),
    url(r'^logout/$', logout),
]
