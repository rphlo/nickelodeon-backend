import datetime
import json
import os.path
import re
import urllib
from random import randint

from celery.app import control
from celery.result import AsyncResult
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from knox.models import AuthToken
from knox.serializers import UserSerializer
from rest_framework import generics, parsers, renderers, status
from rest_framework.authtoken.serializers import AuthTokenSerializer
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import SAFE_METHODS, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from resumable.files import ResumableFile

from nickelodeon.api.forms import ResumableMp3UploadForm
from nickelodeon.api.serializers import ChangePasswordSerializer, MP3SongSerializer
from nickelodeon.models import MP3Song
from nickelodeon.tasks import (
    create_aac,
    fetch_spotify_track,
    fetch_youtube_video,
    move_files_to_destination,
)
from nickelodeon.utils import print_vinyl, s3_object_url

MAX_SONGS_LISTED = 999


def x_accel_redirect(request, path, filename="", mime="application/force-download"):
    if settings.DEBUG:
        import os.path
        from wsgiref.util import FileWrapper

        path = re.sub(r"^/internal", settings.NICKELODEON_MUSIC_ROOT, path)
        if not os.path.exists(path):
            return HttpResponse(status=status.HTTP_404_NOT_FOUND)
        wrapper = FileWrapper(open(path, "rb"))
        response = HttpResponse(wrapper)
        response["Content-Length"] = os.path.getsize(path)
    else:
        response = HttpResponse("", status=status.HTTP_206_PARTIAL_CONTENT)
        response["X-Accel-Redirect"] = urllib.parse.quote(path.encode("utf-8"))
        response["X-Accel-Buffering"] = "no"
        response["Accept-Ranges"] = "bytes"
    response["Content-Type"] = mime
    prefix = "" if dl else ""
    return 
    response["Content-Disposition"] = f"attachment; {prefix}filename*=UTF-8''{urllib.parse.quote(filename, safe='')}"
    return response


def serve_from_s3(request, path, filename="", mime="application/force-download"):
    path = re.sub(r"^/internal/", "", path)
    url = s3_object_url(path)
    url = "/s3_proxy{}".format(url[len(settings.S3_ENDPOINT_URL) :])
    response_status = status.HTTP_200_OK
    if request.method == "GET":
        response_status = status.HTTP_206_PARTIAL_CONTENT

    response = HttpResponse("", status=response_status)
    if request.method == "GET":
        response["X-Accel-Redirect"] = urllib.parse.quote(url.encode("utf-8"))
        response["X-Accel-Buffering"] = "no"
    response["Accept-Ranges"] = "bytes"
    response["Content-Type"] = mime
    final_filename = filename.replace("\\", "_").replace('"', '\\"')
    response["Content-Disposition"] = f'attachment; filename="{final_filename}"'
    return response


@api_view(["GET"])
@permission_classes((IsAuthenticated,))
def download_song(request, pk, extension=None):
    if extension is None:
        extension = "mp3"
    song = get_object_or_404(MP3Song.objects.select_related("owner"), pk=pk)
    # if song.owner != request.user:
    #    return HttpResponse(status=status.HTTP_404_NOT_FOUND)
    file_path = song.filename
    mime = "audio/mpeg" if extension == "mp3" else "audio/x-m4a"
    file_path = "{}.{}".format(file_path, extension)
    file_path = "/internal/{}/{}".format(song.owner.settings.storage_prefix, file_path)
    filename = song.title + "." + extension
    return serve_from_s3(request, file_path, filename=filename, mime=mime)


@api_view(["GET"])
@permission_classes((IsAuthenticated,))
def download_cover(request, pk):
    song = get_object_or_404(MP3Song.objects.select_related("owner"), pk=pk)
    # if song.owner != request.user:
    #    return HttpResponse(status=status.HTTP_404_NOT_FOUND)
    file_path = "{}/{}".format(song.owner.settings.storage_prefix, song.filename)
    image = print_vinyl(file_path)
    response = HttpResponse(content_type="image/jpeg")
    image.save(response, "png")
    return response


class RandomSongView(generics.RetrieveAPIView):
    serializer_class = MP3SongSerializer
    queryset = MP3Song.objects.select_related("owner").all()
    permission_classes = (IsAuthenticated,)

    # def get_queryset(self):
    #    return super().get_queryset().filter(owner=self.request.user)

    @transaction.atomic
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
            prev_pwd = serializer.validated_data.get("old_password", "")
            if not prev_pwd or not request.user.check_password(prev_pwd):
                raise ValidationError("Password incorrect")
            new_password = serializer.create(serializer.validated_data)
            request.user.set_password(new_password)
            request.user.save()
            return Response("Password changed")
        return Response("Password change failed", status=400)


class SongView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MP3SongSerializer
    queryset = MP3Song.objects.select_related("owner").all()
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        if (
            self.request.method not in SAFE_METHODS
            and not self.request.user.is_superuser
        ):
            return super().get_queryset().filter(owner=self.request.user)
        return super().get_queryset()

    def perform_destroy(self, instance):
        instance.remove_file()
        super(SongView, self).perform_destroy(instance)


class TextSearchApiView(generics.ListAPIView):
    """
    Search Songs API

    q -- Search terms (Default: '')
    """

    queryset = MP3Song.objects.select_related("owner").all()
    serializer_class = MP3SongSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        qs = super(TextSearchApiView, self).get_queryset()
        try:
            only_own = bool(self.request.query_params.get("o", "").strip())
        except Exception:
            pass
        if only_own:
            qs = qs.filter(owner=self.request.user)
        search_text = self.request.query_params.get("q", "").strip()
        if search_text:
            quoted_terms = re.findall(r"\"(.+?)\"", search_text)
            if quoted_terms:
                search_text = re.sub(r"\"(.+?)\"", "", search_text)
            search_terms = search_text.split(" ")
            query = Q()
            for search_term in search_terms + quoted_terms:
                if (
                    settings.DATABASES["default"]["ENGINE"]
                    == "django.db.backends.postgresql_psycopg2"
                ):
                    key = "filename__unaccent__icontains"
                else:
                    key = "filename__icontains"
                query &= Q(**{key: search_term})
            qs = qs.filter(query)
        else:
            return qs.none()
        qs = qs.order_by("filename")[:MAX_SONGS_LISTED]
        return qs


@api_view(["GET"])
def api_root(request):
    if request.user.is_authenticated:
        return Response(
            {
                "status": "logged in",
                "username": request.user.username,
                "is_superuser": request.user.is_superuser,
            }
        )
    return Response({"status": "logged out"})


@api_view(["GET"])
@permission_classes((IsAdminUser,))
def tasks_list(request):
    i = control.inspect()
    return Response(i.active())


@api_view(["GET"])
@permission_classes((IsAuthenticated,))
def task_status(request, task_id):
    res = AsyncResult(task_id)
    try:
        data = json.dumps(res.info)
        return Response(res.info)
    except Exception:
        return Response({"error": "Something went wrong"})


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def youtube_grab(request):
    video_id = request.data.get("v", "")
    if not re.match(r"[a-zA-Z0-9_-]{11}", video_id):
        raise ValidationError("Invalid v parameter %s" % video_id)
    task = fetch_youtube_video.s(request.user.id, video_id).delay()
    return Response({"task_id": str(task.task_id)})


@api_view(["POST"])
@permission_classes((IsAuthenticated,))
def spotify_grab(request):
    track_id = request.data.get("s", "")
    if not re.match(r"[0-9a-zA-Z]{22}", track_id):
        raise ValidationError("Invalid s parameter %s" % track_id)
    task = fetch_spotify_track.s(request.user.id, track_id).delay()
    return Response({"task_id": str(task.task_id)})


class LoginView(GenericAPIView):
    """
    Login View: mix of knox login view and drf obtain auth token view
    """

    throttle_classes = ()
    permission_classes = ()
    parser_classes = (
        parsers.FormParser,
        parsers.MultiPartParser,
        parsers.JSONParser,
    )
    renderer_classes = (renderers.JSONRenderer,)
    serializer_class = AuthTokenSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        _, token = AuthToken.objects.create(user)
        user_logged_in.send(sender=user.__class__, request=request, user=user)
        return Response(
            {
                "user": UserSerializer(
                    user, context=self.get_serializer_context()
                ).data,
                "token": token,
                "is_staff": True,
                "is_superuser": user.is_superuser,
            }
        )


class ResumableUploadView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        """
        Checks if chunk has already been sent.
        """

        if not request.GET.get("resumableFilename"):
            return render(request, "upload.html", {"form": ResumableMp3UploadForm()})
        rf = ResumableFile(self.storage, request.GET)
        if not (rf.chunk_exists or rf.is_complete):
            return HttpResponse("chunk not found", status=404)
        return HttpResponse("chunk already exists")

    def post(self, request, *args, **kwargs):
        """
        Saves chunks then checks if the file is complete.
        """
        chunk = request.FILES.get("file")
        rf = ResumableFile(self.storage, request.POST)
        ext = rf.filename[rf.filename.rfind(".") :]
        if ext.lower() != ".mp3":
            return HttpResponse("Only MP3 files are allowed", status=400)
        if rf.chunk_exists and not rf.is_complete:
            return HttpResponse("chunk already exists")
        elif not rf.chunk_exists:
            rf.process_chunk(chunk)
        if rf.is_complete:
            self.process_file(request.user, request.POST.get("resumableFilename"), rf)
            rf.delete_chunks()
        return HttpResponse()

    def process_file(self, user, filename, rfile):
        """
        Process the complete file.
        """
        root_folder = user.settings.storage_prefix
        if not self.storage.exists(rfile.filename):
            self.storage.save(rfile.filename, rfile)
        now = datetime.datetime.now()
        dest = os.path.join(root_folder, "Assorted", "by_date", now.strftime("%Y/%m"))
        mp3_path = os.path.abspath(os.path.join(self.chunks_dir, rfile.filename))
        final_filename = move_files_to_destination(
            dest, filename[:-4], ["mp3"], {"mp3": mp3_path}
        )
        final_path = os.path.join(dest, final_filename)
        mp3 = MP3Song.objects.create(
            filename=final_path[len(root_folder) + 1 :], aac=False, owner=user
        )
        create_aac.s(mp3.id).delay()
        return True

    @property
    def chunks_dir(self):
        chunks_dir = getattr(settings, "FILE_UPLOAD_TEMP_DIR", None)
        if not chunks_dir:
            raise ImproperlyConfigured("You must set settings.FILE_UPLOAD_TEMP_DIR")
        return chunks_dir

    @property
    def storage(self):
        return FileSystemStorage(location=self.chunks_dir)
