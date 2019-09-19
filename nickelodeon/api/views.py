import datetime
import os.path
import re
import urllib
from random import randint

from knox.auth import TokenAuthentication
from knox.models import AuthToken
from knox.serializers import UserSerializer

from django.conf import settings
from django.contrib.auth.models import User
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
from rest_framework.views import APIView

from celery.result import AsyncResult
from celery.task.control import inspect

from resumable.files import ResumableFile

from nickelodeon.api.forms import ResumableMp3UploadForm
from nickelodeon.api.serializers import MP3SongSerializer, ChangePasswordSerializer
from nickelodeon.models import MP3Song
from nickelodeon.tasks import fetch_youtube_video, create_aac
from nickelodeon.utils import s3_object_url, print_vinyl
from nickelodeon.tasks import move_files_to_destination


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
    path = re.sub(r'^/internal/', '', path)
    url = s3_object_url(path)
    url = '/wasabi{}'.format(url[len(settings.S3_ENDPOINT_URL):])
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
    if song.owner != request.user:
        return HttpResponse(status=status.HTTP_404_NOT_FOUND)
    file_path = song.filename
    mime = 'audio/mpeg' if extension == 'mp3' else 'audio/x-m4a'
    file_path = u'{}.{}'.format(file_path, extension)
    file_path = u'/internal/{}/{}'.format(
        song.owner.username,
        file_path
    )
    filename = song.title + '.' + extension
    return serve_from_s3(request, file_path, filename=filename, mime=mime)


@api_view(['GET'])
@permission_classes((IsAuthenticated, ))
def download_cover(request, pk):
    song = get_object_or_404(MP3Song, pk=pk)
    if song.owner != request.user:
        return HttpResponse(status=status.HTTP_404_NOT_FOUND)
    file_path = u'{}/{}'.format(
        song.owner.username,
        song.filename
    )
    image = print_vinyl(file_path)
    response = HttpResponse(content_type="image/jpg")
    image.save(response, 'png')
    return response


class RandomSongView(generics.RetrieveAPIView):
    serializer_class = MP3SongSerializer
    queryset = MP3Song.objects.all()
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)

    def get_object(self):
        count = self.get_queryset().count()
        if count == 0:
            raise NotFound
        random_index = randint(0, count - 1)
        return self.get_queryset()[random_index]


class PasswordChangeView(APIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = (IsAuthenticated,)

    def put(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            prev_pwd = serializer.validated_data.get('old_password', '')
            if not prev_pwd or not request.user.check_password(prev_pwd):
                raise ValidationError('Password incorrect'+prev_pwd)
            new_password = serializer.create(serializer.validated_data)
            request.user.set_password(new_password)
            return Response('Password changed')
        return Response('Password change failed', status=400)


class SongView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MP3SongSerializer
    queryset = MP3Song.objects.all()
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)

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
        qs = qs.filter(owner=self.request.user)
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
@permission_classes((IsAuthenticated, ))
def task_status(request, task_id):
    res = AsyncResult(task_id)
    return Response(res.info)


@api_view(['POST'])
@permission_classes((IsAuthenticated, ))
def youtube_grab(request):
    video_id = request.data.get('v', '')
    if not re.match(r'[a-zA-Z0-9_-]{11}', video_id):
        raise ValidationError('Invalid v parameter %s' % video_id)
    task = fetch_youtube_video.s(request.user.id, video_id).delay()
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
            'is_staff': True
        })


class ResumableUploadView(APIView):
    permission_classes = (IsAuthenticated,)

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
        rf = ResumableFile(self.storage, request.GET)
        if not (rf.chunk_exists or rf.is_complete):
            return HttpResponse('chunk not found', status=404)
        return HttpResponse('chunk already exists')

    def post(self, request, *args, **kwargs):
        """
        Saves chunks then checks if the file is complete.
        """
        chunk = request.FILES.get('file')
        rf = ResumableFile(self.storage, request.POST)
        if rf.filename[-4:] != '.mp3':
            return HttpResponse('Only MP3 files are allowed', status=400)
        if rf.chunk_exists:
            return HttpResponse('chunk already exists')
        rf.process_chunk(chunk)
        if rf.is_complete:
            self.process_file(request.user, rf.filename, rf)
            rf.delete_chunks()
        return HttpResponse()

    def process_file(self, user, filename, rfile):
        """
        Process the complete file.
        """
        username = user.username
        if not self.storage.exists(rfile.filename):
            self.storage.save(rfile.filename, rfile)
        now = datetime.datetime.now()
        dest = os.path.join(
            username, 'Assorted', 'by_date', now.strftime('%Y/%m')
        )
        filename = filename[filename.find('_') + 1:]
        mp3_path = os.path.abspath(
            os.path.join(self.chunks_dir, rfile.filename)
        )
        final_filename = move_files_to_destination(
            dest,
            filename[:-4],
            ['mp3'],
            {'mp3': mp3_path}
        )
        final_path = os.path.join(
            dest,
            final_filename
        )
        mp3 = MP3Song.objects.create(
            filename=final_path[len(username)+1:],
            aac=False,
            owner=user
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
