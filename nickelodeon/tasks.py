import datetime
import logging
import os
import os.path
import tempfile

import yt_dlp
from celery import current_task, shared_task
from celery.exceptions import Ignore
from django.conf import settings
from django.contrib.auth.models import User
from librespot.audio.decoders import AudioQuality, VorbisOnlyAudioQuality
from librespot.core import Session as SpotSession
from librespot.metadata import TrackId as SpotTrackId

from nickelodeon.models import MP3Song
from nickelodeon.utils import (
    AVAILABLE_FORMATS,
    convert_audio,
    ffmpeg_has_lib,
    s3_object_exists,
    s3_object_url,
    s3_upload,
    s3_move_object,
)

logger = logging.getLogger(__name__)


@shared_task()
def move_file(instance_id, from_filename, to_filename):
    song = None
    try:
        song = MP3Song.objects.get(id=instance_id)
    except MP3Song.DoesNotExist:
        return
    song.filename = from_filename
    try:
        song.move_file_to(to_filename)
        song.filename = to_filename
    except Exception:
        pass
    finally:    
        song.save()


@shared_task()
def create_aac(mp3_id=""):
    song = None
    try:
        song = MP3Song.objects.get(id=mp3_id)
    except MP3Song.DoesNotExist:
        return
    if not song.has_aac and song.has_mp3:
        mp3_path = song.get_file_format_path("mp3")
        aac_path = song.get_file_format_path("aac")
        mp3_url = s3_object_url(mp3_path)
        with tempfile.NamedTemporaryFile() as aac_file:
            aac_tmp_path = aac_file.name
        convert_audio(
            mp3_url,
            output_file_aac=aac_tmp_path,
        )
        with open(aac_tmp_path, mode="rb") as f:
            s3_upload(f, aac_path)
    if not song.aac:
        song.aac = True
        song.save()
    return {"done": "ok"}


@shared_task()
def fetch_youtube_video(user_id="", video_id=""):
    safe_title = ""
    current_task.update_state(
        state="PROGRESS",
        meta={
            "description": "initialized",
        },
    )

    try:
        user = User.objects.get(id=user_id)
        root_folder = user.settings.storage_prefix
    except User.DoesNotExist:
        current_task.update_state(
            state="FAILED", meta={"error": "User does not exists"}
        )
        logger.error("User does not exists")
        raise Ignore()

    def update_dl_progress(progress_stats):
        current_task.update_state(
            state="PROGRESS",
            meta={
                "description": "downloading",
                "current": progress_stats * 100,
                "total": 100,
                "step": 1,
                "step_total": 2,
                "song_name": safe_title,
            },
        )

    def update_conversion_progress(progress_stats):
        current_task.update_state(
            state="PROGRESS",
            meta={
                "description": "converting audio",
                "current": progress_stats * 100,
                "total": 100,
                "step": 2,
                "step_total": 2,
                "song_name": safe_title,
            },
        )

    extension_converted = []
    for ext, lib in AVAILABLE_FORMATS.items():
        if ffmpeg_has_lib(lib) or ext == "aac":
            extension_converted.append(ext)
    if not extension_converted:
        current_task.update_state(
            state="FAILED", meta={"error": "FFMPEG not properly configured"}
        )
        logger.error("ffmpeg can not do the necesary file conversions")
        raise Ignore()

    with tempfile.NamedTemporaryFile() as download_file:
        download_path = download_file.name

    tmp_paths = {}
    for ext, lib in AVAILABLE_FORMATS.items():
        if ext in extension_converted:
            with tempfile.NamedTemporaryFile() as tmp_file:
                tmp_paths[ext] = tmp_file.name
    now = datetime.datetime.now()
    dst_folder = os.path.join(root_folder, "Assorted", "by_date", now.strftime("%Y/%m"))

    update_dl_progress(0)
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "ignoreerrors": False,
        "outtmpl": download_path + ".%(ext)s",
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info_dict = ydl.extract_info(video_id, download=False)
            title = info_dict.get("title", None)
            safe_title = (
                title.replace("<", "")
                .replace(">", "")
                .replace(":", "")
                .replace("\\", "")
                .replace("/", "")
                .replace('"', "")
                .replace("|", "")
                .replace("?", "")
                .replace("*", "")
            )
            update_dl_progress(0)
            ydl.download([video_id])
        except Exception as e:
            current_task.update_state(
                state="FAILED",
                meta={
                    "error": "Could not retrieve YouTube video audiostream (%s, %r)"
                    % (str(e), e.args)
                },
            )
            raise Ignore()
    update_dl_progress(1)
    tmp_paths["mp3"] = download_path + ".mp3"
    convert_audio(
        tmp_paths["mp3"], tmp_paths.get("aac"), callback=update_conversion_progress
    )
    final_filename = move_files_to_destination(
        dst_folder, safe_title, extension_converted, tmp_paths
    )
    song_filename = os.path.join(dst_folder, final_filename)
    song, dummy_created = MP3Song.objects.get_or_create(
        filename=song_filename[len(root_folder) + 1 :],
        aac=("aac" in extension_converted),
        owner=user,
    )
    return {
        "pk": song.pk,
        "youtube_id": video_id,
        "filename": song_filename[len(root_folder) + 1 :],
    }


@shared_task()
def fetch_spotify_track(user_id="", track_id=""):
    current_task.update_state(
        state="PROGRESS",
        meta={
            "description": "initialized",
        },
    )
    safe_title = ""
    try:
        user = User.objects.get(id=user_id)
        root_folder = user.settings.storage_prefix
    except User.DoesNotExist:
        current_task.update_state(
            state="FAILED", meta={"error": "User does not exists"}
        )
        logger.error("User does not exists")
        raise Ignore()

    def update_dl_progress(progress_stats):
        current_task.update_state(
            state="PROGRESS",
            meta={
                "description": "downloading",
                "current": progress_stats * 100,
                "total": 100,
                "step": 1,
                "step_total": 2,
                "song_name": safe_title,
            },
        )

    def update_conversion_progress(progress_stats):
        current_task.update_state(
            state="PROGRESS",
            meta={
                "description": "converting audio",
                "current": progress_stats * 100,
                "total": 100,
                "step": 2,
                "step_total": 2,
                "song_name": safe_title,
            },
        )

    extension_converted = []
    for ext, lib in AVAILABLE_FORMATS.items():
        if ffmpeg_has_lib(lib) or ext == "aac":
            extension_converted.append(ext)
    if not extension_converted:
        current_task.update_state(
            state="FAILED", meta={"error": "FFMPEG not properly configured"}
        )
        logger.error("ffmpeg can not do the necesary file conversions")
        raise Ignore()

    with tempfile.NamedTemporaryFile() as download_file:
        download_path = download_file.name

    tmp_paths = {}
    for ext, lib in AVAILABLE_FORMATS.items():
        if ext in extension_converted:
            with tempfile.NamedTemporaryFile() as tmp_file:
                tmp_paths[ext] = tmp_file.name
    now = datetime.datetime.now()
    dst_folder = os.path.join(root_folder, "Assorted", "by_date", now.strftime("%Y/%m"))

    update_dl_progress(0)
    session = None
    if os.path.isfile("credentials.json"):
        try:
            session = SpotSession.Builder().stored_file().create()
        except RuntimeError:
            pass
    if session is None or not session.is_valid():
        username = settings.SPOTIFY_USERNAME
        password = settings.SPOTIFY_PASSWORD
        session = SpotSession.Builder().user_pass(username, password).create()
        if not session.is_valid():
            current_task.update_state(
                state="FAILED",
                meta={"error": "Could not login spotify"},
            )
            raise Ignore()
    strack_id = SpotTrackId.from_base62(track_id)
    original = session.api().get_metadata_4_track(strack_id)
    track = session.content_feeder().pick_alternative_if_necessary(original)
    if not track:
        current_task.update_state(
            state="FAILED",
            meta={"error": "Could not find track"},
        )
        raise Ignore()
    title = f'{", ".join([a.name for a in track.artist])} - {track.name}'
    safe_title = (
        title.replace("<", "")
        .replace(">", "")
        .replace(":", "")
        .replace("\\", "")
        .replace("/", "")
        .replace('"', "")
        .replace("|", "")
        .replace("?", "")
        .replace("*", "")
    )
    update_dl_progress(0)
    stream = session.content_feeder().load(
        strack_id, VorbisOnlyAudioQuality(AudioQuality.VERY_HIGH), False, None
    )
    end = stream.input_stream.stream().size()
    with open(download_path + ".ogg", "wb") as fp:
        while True:
            if stream.input_stream.stream().pos() >= end:
                break
            byte = stream.input_stream.stream().read()
            if byte:
                fp.write(bytes(byte))
    update_dl_progress(1)
    convert_audio(
        download_path + ".ogg",
        tmp_paths.get("aac"),
        tmp_paths.get("mp3"),
        callback=update_conversion_progress,
    )
    final_filename = move_files_to_destination(
        dst_folder, safe_title, extension_converted, tmp_paths
    )
    song_filename = os.path.join(dst_folder, final_filename)
    song, dummy_created = MP3Song.objects.get_or_create(
        filename=song_filename[len(root_folder) + 1 :],
        aac=("aac" in extension_converted),
        owner=user,
    )
    return {
        "pk": song.pk,
        "track_id": track_id,
        "filename": song_filename[len(root_folder) + 1 :],
    }


def move_files_to_destination(dst_folder, safe_title, extensions, tmp_paths):
    filename = safe_title
    attempt = 0
    while True:
        file_exist = False
        for ext, lib in AVAILABLE_FORMATS.items():
            if attempt == 0:
                filename = "{}.{}".format(safe_title, ext)
            else:
                filename = "{} ({}).{}".format(safe_title, attempt, ext)
            final_path = os.path.join(dst_folder, filename)
            if ext in extensions and s3_object_exists(final_path):
                file_exist = True
                break
        if not file_exist:
            break
        attempt += 1
    for ext, lib in AVAILABLE_FORMATS.items():
        if ext in extensions:
            if attempt == 0:
                filename = safe_title
            else:
                filename = "{} ({})".format(safe_title, attempt)
            final_path = os.path.join(dst_folder, filename + "." + ext)
            with open(tmp_paths[ext], mode="rb") as f:
                s3_upload(f, final_path)
            os.remove(tmp_paths[ext])
    return filename
