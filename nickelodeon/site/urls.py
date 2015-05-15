from django.conf.urls import url, include
from django.views.generic import TemplateView
from django.contrib import admin
from django.contrib.auth.views import login, logout
from django.contrib.auth.decorators import permission_required


urlpatterns = [
    url(r'^(listen/?)?$',
        view=permission_required('nickelodeon.can_listen_song')(
            TemplateView.as_view(template_name="nickelodeon/music_player.html")
        ),
        name='default_view'),
    url(r'^listen/(?P<pk>[a-zA-Z0-9]{11})/?$',
        view=permission_required('nickelodeon.can_listen_song')(
            TemplateView.as_view(template_name="nickelodeon/music_player.html")
        ),
        name='song_view'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^login/$', login),
    url(r'^logout/$', logout),
    url(r'^api/', include('nickelodeon.api.urls')),
]
