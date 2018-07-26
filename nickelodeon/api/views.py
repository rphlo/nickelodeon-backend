import re
import urllib

from knox.models import AuthToken
from knox.serializers import UserSerializer
from random import randint

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from rest_framework import parsers, generics, renderers
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.decorators import (
    api_view,
    permission_classes,
    renderer_classes,
)
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response

from celery.result import AsyncResult

from nickelodeon.api.serializers import MP3SongSerializer
from nickelodeon.models import MP3Song
from nickelodeon.tasks import fetch_youtube_video


class MP3Renderer(BaseRenderer):
    """ Renderer for MP3 binary content. """
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
        if not os.path.exists(path):
            return HttpResponse(status=404)
        wrapper = FileWrapper(open(path, 'rb'))
        response = HttpResponse(wrapper)
        response['Content-Length'] = os.path.getsize(path)
    else:
        response = HttpResponse('', status=206)
        response['X-Accel-Redirect'] = urllib.parse.quote(path.encode('utf-8'))
        response['X-Accel-Buffering'] = 'no'
        response['Accept-Ranges'] = 'bytes'
    response['Content-Type'] = mime
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(
        filename.replace('\\', '_').replace('"', '\\"')
    )
    return response


@api_view(['GET'])
def api_root(request, format=None):
    return Response({
        'songs': reverse('user-list', request=request, format=format),
        'snippets': reverse('snippet-list', request=request, format=format)
    })



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

@api_view(['GET'])
def api_root(request):
    return Response('')


@api_view(['GET'])
def task_status(request, task_id):
    res = AsyncResult(task_id)
    status = res.info
    return Response(status)

@api_view(['POST'])
@permission_classes((IsAuthenticated, ))
def youtube_grab(request):
    video_id = request.POST.get('v', '')
    if not re.match(r'[a-zA-Z0-9_-]{11}', video_id):
        raise ValidationError('Invalid v parameter')
    task = fetch_youtube_video.s(video_id).delay()
    return Response({'task_id': str(task.task_id)})


class LoginView(GenericAPIView):
    """
    Login View: mix of knox login view and drf obtain auth token view
    """
    throttle_classes = ()
    permission_classes = ()
    parser_classes = (parsers.FormParser, parsers.MultiPartParser,
                      parsers.JSONParser,)
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = AuthTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token = AuthToken.objects.create(user)
        user_logged_in.send(sender=user.__class__,
                            request=request,
                            user=user)
        return Response({
            'user': UserSerializer(user,
                                   context=self.get_serializer_context()).data,
            'token': token
        })
