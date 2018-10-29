from django.conf.urls import url, include

urlpatterns = [
    url(r'^drf-auth/', include('rest_framework.urls',
                               namespace='rest_framework')),
    url(r'^', include('nickelodeon.api.urls')),
]
