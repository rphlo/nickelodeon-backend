from __future__ import absolute_import
import time
from celery import shared_task


@shared_task
def fetch_youtube_video_infos(id=''):
    time.sleep(30)
    return "infos for {0}".format(str(id))
