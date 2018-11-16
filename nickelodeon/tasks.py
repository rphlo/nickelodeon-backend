import datetime
import os
from subprocess import call

from celery import shared_task, current_task
import logging
import pafy
from celery.exceptions import Ignore

from django.conf import settings
from django.core.files.move import file_move_safe

from nickelodeon.models import MP3Song
from nickelodeon.utils import (
    convert_audio,
    ffmpeg_has_lib,
    AVAILABLE_FORMATS
)

logger = logging.getLogger(__name__)

@shared_task()
def fetch_youtube_video(video_id=''):
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
    download_path = os.path.join('/tmp', video_id + '.m4a')
    tmp_paths = {}
    for ext, lib in AVAILABLE_FORMATS.items():
        if ext in extension_converted:
            tmp_paths[ext] = os.path.join('/tmp', safe_title + '.' + ext)
    now = datetime.datetime.now()
    dst_folder = os.path.join(
        settings.NICKELODEON_MUSIC_ROOT,
        'rphl', 'Assorted', 'by_date', now.strftime('%Y/%m')
    )
    #audio_stream.download(
    #    download_path,
    #    callback=update_dl_progress,
    #    quiet=True
    #)
    update_dl_progress(0)
    status = call(
        'youtube-dl --quiet -x --audio-format m4a -o {} '
        'https://www.youtube.com/watch?v={}'
            .format(download_path, video_id),
        shell=True
    )
    if status != 0:
        current_task.update_state(
            state='FAILED',
            meta={'error': 'Youtube-DL returned an error'}
        )
        logger.error(
            'Youtube-DL returned with an error code '
            'for video %s', video_id
        )
        raise Ignore()
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
    offset = 0 if settings.NICKELODEON_MUSIC_ROOT[-1] == '/' else 1
    song_filename = os.path.join(
        dst_folder,
        final_filename
    )[len(settings.NICKELODEON_MUSIC_ROOT)+offset:]
    song, dummy_created = MP3Song.objects.get_or_create(
        filename=song_filename,
        aac=('aac' in extension_converted)
    )
    return {'pk': song.pk, 'youtube_id': video_id}


def move_files_to_destination(dst_folder, safe_title, extensions, tmp_paths):
    if not os.path.isdir(dst_folder):
        os.makedirs(dst_folder)
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
            if ext in extensions and os.path.exists(final_path):
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
            file_move_safe(tmp_paths[ext], final_path)
    return filename
