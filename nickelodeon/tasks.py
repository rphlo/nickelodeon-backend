import datetime
import os

from celery import shared_task, current_task
import pafy

from django.conf import settings
from django.core.files.move import file_move_safe

from nickelodeon.models import MP3Song
from nickelodeon.utils import (
    convert_audio,
    has_ffmpeg_libmp3lame,
    has_ffmpeg_libfdk_aac,
)


@shared_task()
def fetch_youtube_video(video_id=''):
    def update_dl_progress(*progress_stats):
        current_task.update_state(state='PROGRESS',
                                  meta={'description': 'downloading',
                                        'current': progress_stats[2] * 100,
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

    convert_to_mp3 = has_ffmpeg_libmp3lame()
    convert_to_aac = has_ffmpeg_libfdk_aac()
    if not convert_to_aac and not convert_to_mp3:
        return 'ffmpeg can not do the necesary file conversions'
    try:
        video = pafy.new(video_id)
    except (ValueError, IOError):
        current_task.update_state(state='FAILED',
                                  meta={'error': 'Could not retrieve '
                                                 'YouTube video'})
        return 'Could not retrieve YouTube video {}'.format(video_id)
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
        return ('Could not find proper audio stream '
                'for Youtube video {}').format(video_id)
    download_path = os.path.join("/tmp/", safe_title+".m4a")
    aac_tmp_path = None
    if convert_to_aac:
        aac_tmp_path = os.path.join("/tmp/", safe_title+".aac")
    mp3_tmp_path = None
    if convert_to_mp3:
        mp3_tmp_path = os.path.join("/tmp/", safe_title+".mp3")
    now = datetime.datetime.now()
    dst_folder = os.path.join(
        settings.NICKELODEON_MUSIC_ROOT,
        'rphl', 'Assorted', 'by_date', now.strftime('%Y/%m')
    )
    audio_stream.download(download_path, callback=update_dl_progress,
                          quiet=True)
    convert_audio(download_path, aac_tmp_path, mp3_tmp_path,
                  callback=update_conversion_progress)
    if not os.path.isdir(dst_folder):
        os.makedirs(dst_folder)
    if convert_to_aac:
        aac_path = os.path.join(dst_folder, safe_title + ".aac")
        file_move_safe(aac_tmp_path, aac_path)
    if convert_to_mp3:
        mp3_path = os.path.join(dst_folder, safe_title + ".mp3")
        file_move_safe(mp3_tmp_path, mp3_path)
    os.remove(download_path)
    offset = 0 if settings.NICKELODEON_MUSIC_ROOT[-1] == '/' else 1
    song_fn = os.path.join(
        dst_folder,
        safe_title
    )[len(settings.NICKELODEON_MUSIC_ROOT)+offset:]
    song, dummy_created = MP3Song.objects.get_or_create(filename=song_fn)
    return {'pk': song.pk}
