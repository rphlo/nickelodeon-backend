from __future__ import absolute_import
import datetime
import os
import pafy
from django.utils.translation import ugettext as _
from django.conf import settings
from celery import shared_task, current_task
from zippy import ZippyshareHelper
from nickelodeon.models import Song, YouTubeDownloadTask, Mp3DownloadTask
from nickelodeon.utils import file_move_safe, convert_audio


@shared_task()
def fetch_zippyshare_mp3(zippy_url=''):
    def update_dl_progress(*progress_stats):
        current_task.update_state(state='PROGRESS',
                                  meta={'description': _('downloading'),
                                        'current': progress_stats*100,
                                        'total': 100,
                                        'step': 1,
                                        'step_total': 2})

    def update_conversion_progress(progress_stats):
        current_task.update_state(state='PROGRESS',
                                  meta={'description': _('converting audio'),
                                        'current': progress_stats*100,
                                        'total': 100,
                                        'step': 2,
                                        'step_total': 2})

    try:
        media = ZippyshareHelper(zippy_url).retrieve_details()
    except (ValueError, IOError):
        return "Could not retrieve Zippyshare MP3 {}".format(zippy_url)
    title = media.file_name[:-4]
    safe_title = title.replace("<", "")\
                      .replace(">", "")\
                      .replace(":", "")\
                      .replace("\\", "")\
                      .replace("/", "")\
                      .replace('"', "")\
                      .replace("|", "")\
                      .replace("?", "")\
                      .replace("*", "")
    aac_tmp_path = os.path.join("/tmp/", safe_title+".aac")
    mp3_tmp_path = os.path.join("/tmp/", safe_title+".mp3")
    now = datetime.datetime.now()
    dst_folder = os.path.join(
        settings.MEDIA_ROOT,
        'exthd', 'music', 'rphl', 'Assorted', 'me', now.strftime('%Y/%m')
    )
    aac_path = os.path.join(dst_folder, safe_title+".aac")
    mp3_path = os.path.join(dst_folder, safe_title+".mp3")
    media.download(mp3_tmp_path, callback=update_dl_progress,
                   quiet=True)
    convert_audio(mp3_tmp_path, output_file_aac=aac_tmp_path,
                  output_file_mp3=None, callback=update_conversion_progress)
    if not os.path.isdir(dst_folder):
        os.makedirs(dst_folder)
    file_move_safe(aac_tmp_path, aac_path)
    file_move_safe(mp3_tmp_path, mp3_path)
    song_fn = aac_path[len(settings.MEDIA_ROOT):-4]
    song, created = Song.objects.get_or_create(filename=song_fn,
                                               defaults={'title': safe_title})
    Mp3DownloadTask.objects.filter(url=zippy_url).delete()
    return {'pk': song.pk}


@shared_task()
def fetch_youtube_video(video_id=''):
    def update_dl_progress(*progress_stats):
        current_task.update_state(state='PROGRESS',
                                  meta={'description': _('downloading'),
                                        'current': progress_stats[2]*100,
                                        'total': 100,
                                        'step': 1,
                                        'step_total': 2})

    def update_conversion_progress(progress_stats):
        current_task.update_state(state='PROGRESS',
                                  meta={'description': _('converting audio'),
                                        'current': progress_stats*100,
                                        'total': 100,
                                        'step': 2,
                                        'step_total': 2})

    try:
        video = pafy.new(video_id)
    except (ValueError, IOError):
        return "Could not retrieve YouTube video {}".format(video_id)
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
        return "Could not find proper audio stream"
    download_path = os.path.join("/tmp/", safe_title+".m4a")
    aac_tmp_path = os.path.join("/tmp/", safe_title+".aac")
    mp3_tmp_path = os.path.join("/tmp/", safe_title+".mp3")
    now = datetime.datetime.now()
    dst_folder = os.path.join(
        settings.MEDIA_ROOT,
        'exthd', 'music', 'rphl', 'Assorted', 'me', now.strftime('%Y/%m')
    )
    aac_path = os.path.join(dst_folder, safe_title+".aac")
    mp3_path = os.path.join(dst_folder, safe_title+".mp3")
    audio_stream.download(download_path, callback=update_dl_progress,
                          quiet=True)
    convert_audio(download_path, aac_tmp_path, mp3_tmp_path,
                  callback=update_conversion_progress)
    if not os.path.isdir(dst_folder):
        os.makedirs(dst_folder)
    file_move_safe(aac_tmp_path, aac_path)
    file_move_safe(mp3_tmp_path, mp3_path)
    os.remove(download_path)
    song_fn = aac_path[len(settings.MEDIA_ROOT):-4]
    song, created = Song.objects.get_or_create(filename=song_fn,
                                               defaults={'title': safe_title})
    YouTubeDownloadTask.objects.filter(video_id=video_id).delete()
    return {'pk': song.pk}
