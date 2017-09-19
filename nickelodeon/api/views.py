import re
import urllib
from random import randint

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404

from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes, \
    renderer_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response

from nickelodeon.api.serializers import MP3SongSerializer
from nickelodeon.models import MP3Song


class MP3Renderer(BaseRenderer):

    """ Renderer for Mp3 binary content. """

    media_type = 'audio/mpeg'
    format = 'mp3'
    charset = None
    render_style = 'binary'

    def render(self, data, media_type=None, renderer_context=None):
        return data


def x_accel_redirect(request, path, filename='',
                     mime='application/force-download'):
    if settings.DEBUG:
        from wsgiref.util import FileWrapper
        import os.path
        path = re.sub(r'^/internal', settings.NICKELODEON_MUSIC_ROOT, path)
        wrapper = FileWrapper(open(path, 'rb'))
        response = HttpResponse(wrapper, content_type=mime)
        response['Content-Length'] = os.path.getsize(path)
    else:
        response = HttpResponse('', status=206)
        response['X-Accel-Redirect'] = urllib.parse.quote(path.encode('utf-8'))
        response['X-Accel-Buffering'] = 'no'
        response['Accept-Ranges'] = 'bytes'
    response['Content-Disposition'] = "attachment; filename={}".format(
        urllib.parse.quote_plus(filename.encode('utf-8'))
    )
    return response


@api_view(['GET'])
@permission_classes((IsAuthenticated, ))
@renderer_classes((MP3Renderer, ))
def download_song(request, pk, extension=None):
    song = get_object_or_404(MP3Song, pk=pk)
    file_path = song.filename
    if extension is None:
        extension = 'mp3'
    mime = 'audio/mpeg' if extension == 'mp3' else 'audio/x-m4a'
    file_path = u'{}.{}'.format(file_path, extension)
    file_path = u'/internal/{}'.format(file_path)
    filename = song.title + '.' + extension
    return x_accel_redirect(request, file_path, filename=filename, mime=mime)


class RandomSongView(generics.RetrieveAPIView):
    serializer_class = MP3SongSerializer
    queryset = MP3Song.objects.all()
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        count = self.get_queryset().count()
        if count == 0:
            raise NotFound
        random_index = randint(0, count - 1)
        return self.get_queryset()[random_index]


class SongView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MP3SongSerializer
    queryset = MP3Song.objects.all()
    permission_classes = (IsAuthenticated,)

    def perform_destroy(self, instance):
        instance.remove_file()
        super(SongView, self).perform_destroy(instance)


class TextSearchApiView(generics.ListAPIView):
    """
    Search Songs API

    q -- Search terms (Default: '')
    """
    queryset = MP3Song.objects.all()
    serializer_class = MP3SongSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        qs = super(TextSearchApiView, self).get_queryset()
        search_text = self.request.query_params.get('q', '').strip()
        if search_text:
            search_terms = search_text.split(' ')
            query = Q()
            for search_term in search_terms:
                query &= Q(filename__icontains=search_term)
            qs = qs.filter(query)
        else:
            return qs.none()
        qs = qs.order_by('filename')
        return qs
