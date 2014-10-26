from __future__ import absolute_import
import datetime
import pafy
import re
import os
from django.utils.translation import ugettext as _
from django.conf import settings
from celery import shared_task, current_task
import subprocess
from django.core.files.move import file_move_safe
from nickelodeon.models import Song


def convert_audio(input_file, output_file_aac, output_file_mp3, callback=None):
    def parse_ff_time(time_str):
        if not re.match('\d+:\d{2}:\d{2}\.\d+', time_str):
            return 0
        hours, minutes, seconds = [float(x) for x in time_str.split(':')]
        return (hours*60+minutes)*60+seconds

    command = [
        'ffmpeg', '-y', '-i', input_file, '-threads', '0', '-vn',
        '-ar', '44100', '-ac', '2',
        '-b:a', '192k',
        '-f', 'mp3', output_file_mp3,
        '-ar', '44100', '-ac', '2',
        '-b:a', '32k',
        '-c:a', 'libfdk_aac', '-level', '10', '-profile:a', 'aac_he_v2',
        '-movflags', '+faststart', '-cutoff', '20000',
        '-f', 'mp4', output_file_aac
    ]
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               bufsize=10**8)
    duration = ''
    progress = ''
    duration_str = 'Duration: '
    duration_read = False
    read_duration_str_index = 0
    progress_str = 'time='
    read_progress_str_index = 0
    while True:
        out = process.stdout.read(1)
        if out == '' and process.poll() != None:
            break
        if out != '':
            if not duration_read:
                if read_duration_str_index < len(duration_str):
                    if out == duration_str[read_duration_str_index]:
                        read_duration_str_index += 1
                    else:
                        read_duration_str_index = 0
                else:
                    if out != ',':
                        duration += out
                    else:
                        duration_read = True
            if read_progress_str_index < len(progress_str):
                if out == progress_str[read_progress_str_index]:
                    read_progress_str_index += 1
                else:
                    read_progress_str_index = 0
            else:
                if out != ' ':
                    progress += out
                else:
                    if callback:
                        per = parse_ff_time(progress)/parse_ff_time(duration)
                        callback(per)
                    progress = ''
                    read_progress_str_index = 0
    return


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
    audio_stream.download(download_path, callback=update_dl_progress, quiet=True)
    update_conversion_progress(0)
    convert_audio(download_path, aac_tmp_path, mp3_tmp_path,
                  callback=update_conversion_progress)
    update_conversion_progress(100)
    if not os.path.isdir(dst_folder):
        os.makedirs(dst_folder)
    file_move_safe(aac_tmp_path, aac_path)
    file_move_safe(mp3_tmp_path, mp3_path)
    song = Song(filename=aac_path[len(settings.MEDIA_ROOT):-4],
                title=safe_title)
    song.save()
    return song.pk