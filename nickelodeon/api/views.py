import boto3
import datetime
import os.path
import re
import urllib

from django.contrib.auth.decorators import login_required
from django.views.generic import View
from knox.auth import TokenAuthentication
from knox.models import AuthToken
from knox.serializers import UserSerializer
from random import randint

from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from rest_framework import parsers, generics, renderers, status
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from celery.result import AsyncResult
from celery.task.control import inspect
from rest_framework.views import APIView

from resumable.files import ResumableFile

from nickelodeon.api.forms import ResumableMp3UploadForm
from nickelodeon.api.permissions import IsStaffOrReadOnly
from nickelodeon.api.serializers import MP3SongSerializer
from nickelodeon.models import MP3Song
from nickelodeon.tasks import fetch_youtube_video, create_aac
from nickelodeon.utils import get_s3_client


MAX_SONGS_LISTED = 999


def x_accel_redirect(request, path, filename='',
                     mime='application/force-download'):
    if settings.DEBUG:
        from wsgiref.util import FileWrapper
        import os.path
        path = re.sub(r'^/internal', settings.NICKELODEON_MUSIC_ROOT, path)
        if not os.path.exists(path):
            return HttpResponse(status=status.HTTP_404_NOT_FOUND)
        wrapper = FileWrapper(open(path, 'rb'))
        response = HttpResponse(wrapper)
        response['Content-Length'] = os.path.getsize(path)
    else:
        response = HttpResponse('', status=status.HTTP_206_PARTIAL_CONTENT)
        response['X-Accel-Redirect'] = urllib.parse.quote(path.encode('utf-8'))
        response['X-Accel-Buffering'] = 'no'
        response['Accept-Ranges'] = 'bytes'
    response['Content-Type'] = mime
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(
        filename.replace('\\', '_').replace('"', '\\"')
    ).encode('utf-8')
    return response


def serve_from_s3(request, path, filename='',
                  mime='application/force-download'):
    s3 = get_s3_client()
    path = re.sub(r'^/internal/', '', path)
    url = s3.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': settings.S3_BUCKET,
            'Key': path
        }
    )
    url = re.sub(r'^https://s3.wasabisys.com', '/wasabi', url)
    response = HttpResponse('', status=status.HTTP_206_PARTIAL_CONTENT)
    response['X-Accel-Redirect'] = urllib.parse.quote(url.encode('utf-8'))
    response['X-Accel-Buffering'] = 'no'
    response['Accept-Ranges'] = 'bytes'
    response['Content-Type'] = mime
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(
        filename.replace('\\', '_').replace('"', '\\"')
    ).encode('utf-8')
    return response

@api_view(['GET'])
@permission_classes((IsAuthenticated, ))
def download_song(request, pk, extension=None):
    if extension is None:
        extension = 'mp3'
    song = get_object_or_404(MP3Song, pk=pk)
    file_path = song.filename
    mime = 'audio/mpeg' if extension == 'mp3' else 'audio/x-m4a'
    file_path = u'{}.{}'.format(file_path, extension)
    file_path = u'/internal/{}'.format(file_path)
    filename = song.title + '.' + extension
    return serve_from_s3(request, file_path, filename=filename, mime=mime)


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
    permission_classes = (IsStaffOrReadOnly,)

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
        qs = qs.order_by('filename')[:MAX_SONGS_LISTED]
        return qs


@api_view(['GET'])
def api_root(request):
    return Response('')


@api_view(['GET'])
@permission_classes((IsAdminUser, ))
def tasks_list(request):
    i = inspect()
    return Response(i.active())


@api_view(['GET'])
@permission_classes((IsAdminUser, ))
def task_status(request, task_id):
    res = AsyncResult(task_id)
    return Response(res.info)


@api_view(['POST'])
@permission_classes((IsAdminUser, ))
def youtube_grab(request):
    video_id = request.data.get('v', '')
    if not re.match(r'[a-zA-Z0-9_-]{11}', video_id):
        raise ValidationError('Invalid v parameter %s' % video_id)
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
        serializer = self.serializer_class(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token = AuthToken.objects.create(user)
        user_logged_in.send(
            sender=user.__class__,
            request=request,
            user=user
        )
        return Response({
            'user': UserSerializer(
                user,
                context=self.get_serializer_context()
            ).data,
            'token': token,
            'is_staff': user.is_staff
        })


class ResumableUploadView(APIView):
    permission_classes = (IsStaffOrReadOnly,)

    def get(self, request, *args, **kwargs):
        """
        Checks if chunk has already been sent.
        """

        if not request.GET.get('resumableFilename'):
            return render(
                request,
                'upload.html',
                {'form': ResumableMp3UploadForm()}
            )
        r = ResumableFile(self.storage, request.GET)
        if not (r.chunk_exists or r.is_complete):
            return HttpResponse('chunk not found', status=404)
        return HttpResponse('chunk already exists')

    def post(self, request, *args, **kwargs):
        """
        Saves chunks then checks if the file is complete.
        """
        chunk = request.FILES.get('file')
        r = ResumableFile(self.storage, request.POST)
        k = request.POST.get('resumableFilename')
        if r.filename[-4:] != '.mp3':
            raise HttpResponse('Only MP3 files are allowed', status=400)
        if r.chunk_exists:
            return HttpResponse('chunk already exists')
        r.process_chunk(chunk)
        if r.is_complete:
            self.process_file(r.filename, r)
            r.delete_chunks()
        return HttpResponse()

    def process_file(self, filename, file):
        """
        Process the complete file.
        """
        now = datetime.datetime.now()
        dest = os.path.join(
            settings.NICKELODEON_MUSIC_ROOT,
            'rphl', 'Assorted', 'by_date', now.strftime('%Y/%m')
        )
        storage = FileSystemStorage(location=dest)
        filename = filename[filename.find('_') + 1:]
        final_filename = storage.save(filename, file)
        offset = 0 if settings.NICKELODEON_MUSIC_ROOT[-1] == '/' else 1
        final_path = os.path.join(
            dest,
            final_filename[:-4]
        )[len(settings.NICKELODEON_MUSIC_ROOT)+offset:]
        mp3 = MP3Song.objects.create(
            filename=final_path,
            aac=False,
        )
        create_aac.s(mp3.id).delay()
        return True

    @property
    def chunks_dir(self):
        chunks_dir = getattr(settings, 'FILE_UPLOAD_TEMP_DIR', None)
        if not chunks_dir:
            raise ImproperlyConfigured(
                'You must set settings.FILE_UPLOAD_TEMP_DIR'
            )
        return chunks_dir

    @property
    def storage(self):
        return FileSystemStorage(location=self.chunks_dir)