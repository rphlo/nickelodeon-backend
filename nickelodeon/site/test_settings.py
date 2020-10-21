from .settings import *

try:
    from .local_settings import *
except ImportError:
    pass

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'db.sqlite',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

S3_ENDPOINT_URL = 'https://s3.wasabisys.com'
S3_ACCESS_KEY = os.environ.get('S3_ACCESS_KEY', S3_ACCESS_KEY)
S3_SECRET_KEY = os.environ.get('S3_SECRET_KEY', S3_SECRET_KEY)