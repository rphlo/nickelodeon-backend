import datetime
import os
import tempfile
from subprocess import call

import youtube_dl
from celery import shared_task, current_task
import logging
import pafy
from celery.exceptions import Ignore

from django.conf import settings
from django.core.files.move import file_move_safe
from django.contrib.auth.models import User
from nickelodeon.models import MP3Song
from nickelodeon.utils import (
    convert_audio,
    ffmpeg_has_lib,
    AVAILABLE_FORMATS,
    s3_upload,
    s3_object_exists,
    s3_object_url
)

logger = logging.getLogger(__name__)


@shared_task()
def create_aac(mp3_id=''):
    song = None
    try:
        song = MP3Song.objects.get(id=mp3_id)
    except MP3Song.DoesNotExist:
        return
    if not song.has_aac and song.has_mp3:
        mp3_path = song.get_file_format_path('mp3')
        aac_path = song.get_file_format_path('aac')
        mp3_url = s3_object_url(mp3_path)
        with tempfile.NamedTemporaryFile() as aac_file:
            aac_tmp_path = aac_file.name
        convert_audio(
            mp3_url,
            output_file_aac=aac_tmp_path,
        )
        s3_upload(aac_tmp_path, aac_path)
    if not song.aac:
        song.aac = True
        song.save()
    return {'done': 'ok'}

@shared_task()
def fetch_youtube_video(user_id='', video_id=''):
    try:
        user = User.objects.get(id=user_id)
        username = user.username
    except User.DoesNotExist:
        current_task.update_state(
            state='FAILED',
            meta={'error': 'User does not exists'}
        )
        logger.error('User does not exists')
        raise Ignore()
    def update_dl_progress(progress_stats):
        current_task.update_state(state='PROGRESS',
                                  meta={'description': 'downloading',
                                        'current': progress_stats * 100,
                                        'total': 100,
                                        'step': 1,
                                        'step_total': 2})

    def update_conversion_progress(progress_stats):
        current_task.update_state(state='PROGRESS',
                                  meta={'description': 'converting audio',
                                        'current': progress_stats * 100,
                                        'total': 100,
                                        'step': 2,
                                        'step_total': 2})

    extension_converted = []
    for ext, lib in AVAILABLE_FORMATS.items():
        if ffmpeg_has_lib(lib) or ext == 'aac':
            extension_converted.append(ext)
    if not extension_converted:
        current_task.update_state(
            state='FAILED',
            meta={'error': 'FFMPEG not properly configured'}
        )
        logger.error('ffmpeg can not do the necesary file conversions')
        raise Ignore()
    try:
        video = pafy.new(video_id)
    except (ValueError, IOError):
        current_task.update_state(state='FAILED',
                                  meta={'error': 'Could not retrieve '
                                                 'YouTube video'})
        logger.error('Could not retrieve YouTube video %s', video_id)
        raise Ignore()
    title = video.title
    safe_title = title.replace("<", "")\
                      .replace(">", "")\
                      .replace(":", "")\
                      .replace("\\", "")\
                      .replace("/", "")\
                      .replace('"', "")\
                      .replace("|", "")\
                      .replace("?", "")\
                      .replace("*", "")
    audio_stream = video.getbestaudio(preftype='m4a', ftypestrict=True)
    if audio_stream is None:
        current_task.update_state(state='FAILED',
                                  meta={'error': 'Could not retrieve '
                                                 'YouTube video '
                                                 'audiostream'})
        logger.error(
            'Could not find proper audio stream '
            'for Youtube video %s', video_id
        )
        raise Ignore()
    with tempfile.NamedTemporaryFile() as download_file:
        download_path = download_file.name
    tmp_paths = {}
    for ext, lib in AVAILABLE_FORMATS.items():
        if ext in extension_converted:
            with tempfile.NamedTemporaryFile() as tmp_file:
                tmp_paths[ext] = tmp_file.name
    now = datetime.datetime.now()
    dst_folder = os.path.join(
        username, 'Assorted', 'by_date', now.strftime('%Y/%m')
    )
    #audio_stream.download(
    #    download_path,
    #    callback=update_dl_progress,
    #    quiet=True
    #)
    update_dl_progress(0)
    ydl_opts = {
        'format': 'bestaudio',
        'quiet': True,
        'outtmpl': download_path,
        'ignoreerrors': False,
    }
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_id])

    update_dl_progress(1)

    convert_audio(
        download_path,
        tmp_paths.get('aac'),
        tmp_paths.get('mp3'),
        callback=update_conversion_progress
    )

    os.remove(download_path)
    final_filename = move_files_to_destination(
        dst_folder,
        safe_title,
        extension_converted,
        tmp_paths
    )
    song_filename = os.path.join(
        dst_folder,
        final_filename
    )
    song, dummy_created = MP3Song.objects.get_or_create(
        filename=song_filename[len(username)+1:],
        aac=('aac' in extension_converted),
        owner=user
    )
    return {'pk': song.pk, 'youtube_id': video_id}


def move_files_to_destination(dst_folder, safe_title, extensions, tmp_paths):
    filename = safe_title
    attempt = 0
    while True:
        file_exist = False
        for ext, lib in AVAILABLE_FORMATS.items():
            if attempt == 0:
                filename =  '{}.{}'.format(safe_title, ext)
            else:
                filename = '{} ({}).{}'.format(safe_title, attempt, ext)
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
                filename =  safe_title
            else:
                filename = '{} ({})'.format(safe_title, attempt)
            final_path = os.path.join(dst_folder, filename + '.' + ext)
            s3_upload(tmp_paths[ext], final_path)
            os.remove(tmp_paths[ext])
    return filename
