from __future__ import absolute_import
import datetime
import os

from celery import shared_task, current_task
import pafy

from django.conf import settings
from django.core.files.move import file_move_safe
from django.utils.translation import ugettext as _

from nickelodeon.models import Song, YouTubeDownloadTask
from nickelodeon.utils import convert_audio


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
        YouTubeDownloadTask.objects.filter(video_id=video_id).delete()
        current_task.update_state(state='FAILED',
                                  meta={'error': _('Could not retrieve '
                                                   'YouTube video')})
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
        YouTubeDownloadTask.objects.filter(video_id=video_id).delete()
        current_task.update_state(state='FAILED',
                                  meta={'error': _('Could not retrieve '
                                                   'YouTube video '
                                                   'audiostream')})
        return ("Could not find proper audio stream "
                "for Youtube video {}").format(video_id)
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
