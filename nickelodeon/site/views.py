import re
import urllib

from django.shortcuts import get_object_or_404
from django.http import HttpResponse, StreamingHttpResponse
from django.conf import settings
from django.db.models import Q

from rest_framework import generics

from nickelodeon.api.serializers import (SongSerializer,
                                         YouTubeDownloadTaskSerializer)
from nickelodeon.models import Song, YouTubeDownloadTask


def x_accel_redirect(request, path, filename='',
                     mime="application/force-download"):
    if settings.DEBUG:
        from django.core.servers.basehttp import FileWrapper
        import os.path
        path = re.sub(r'^/internal', settings.NICKELODEON_MEDIA_ROOT, path)
        wrapper = FileWrapper(file(path))
        response = StreamingHttpResponse(wrapper, content_type=mime)
        response['Content-Length'] = os.path.getsize(path)
    else:
        response = HttpResponse('', status=206)
        response['X-Accel-Redirect'] = urllib.quote(path.encode('utf-8'))
        response['X-Accel-Buffering'] = 'no'
        response['Accept-Ranges'] = 'bytes'
    response['Content-Type'] = mime
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    return response


def download_song(request, pk, extension=None):
    song = get_object_or_404(Song, pk=pk)
    file_path = song.filename
    if extension is None:
        for ext in ('aac', 'mp3'):
            if song.file_format_available(ext):
                extension = ext
    if extension is None or not song.file_format_available(extension):
        return HttpResponse(status=404)
    mime = 'audio/mpeg' if extension == 'mp3' else 'audio/x-m4a'
    file_path = u'{}.{}'.format(file_path, extension)
    file_path = u"/internal{}".format(file_path)
    filename = song.title + '.' + extension
    return x_accel_redirect(request, file_path, filename=filename, mime=mime)


class YouTubeDownloadApiView(generics.ListCreateAPIView):
    """
    Download YouTube Video API
    v -- Video ID (Default: '')
    page -- Page number (Default: 1)
    results_per_page -- Number of result per page (Default:20 Max: 1000)
    """
    queryset = YouTubeDownloadTask.objects.all()
    serializer_class = YouTubeDownloadTaskSerializer

    def get_queryset(self):
        qs = super(YouTubeDownloadApiView, self).get_queryset()
        video_id = self.request.query_params.get('v', '').strip()
        if video_id:
            qs = qs.filter(video_id=video_id)
        return qs


class SongView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SongSerializer
    queryset = Song.objects.all()

    def perform_destroy(self, instance):
        instance.remove_file()
        super(SongView, self).perform_destroy()


class TextSearchApiView(generics.ListAPIView):
    """
    Search Songs API
    q -- Search terms (Default: '')
    page -- Page number (Default: 1)
    results_per_page -- Number of result per page (Default:20 Max: 1000)
    """
    queryset = Song.objects.all()
    serializer_class = SongSerializer
    lookup_fields = ('filename', 'artist', 'title')

    def get_queryset(self):
        qs = super(TextSearchApiView, self).get_queryset()
        search_text = self.request.query_params.get('q', '').strip()
        if search_text:
            search_terms = search_text.split(' ')
            query = Q()
            for search_term in search_terms:
                sub_query = Q()
                for field_name in self.lookup_fields:
                    kwargs = {}
                    kwargs['%s__icontains' % field_name] = search_term
                    sub_query |= Q(**kwargs)
                query &= sub_query
            qs = qs.filter(query)
        qs = qs.order_by('title', 'artist')
        return qs
