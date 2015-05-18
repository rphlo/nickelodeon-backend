from django.conf import settings
from appconf import AppConf


class NickelodeonConf(AppConf):
    MUSIC_ROOT = '/media/'

    class Meta:
        prefix = 'nickelodeon'