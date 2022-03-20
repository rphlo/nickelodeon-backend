from django.urls import include, path

urlpatterns = [
    path("drf-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("", include("nickelodeon.api.urls")),
]
