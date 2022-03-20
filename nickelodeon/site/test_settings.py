from .settings import *  # noqa: F403, F401

try:
    from .local_settings import *  # noqa: F403, F401
except ImportError:
    pass

import os
from tempfile import mkdtemp

FILE_UPLOAD_TEMP_DIR = mkdtemp()

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "db.sqlite",
        "USER": "",
        "PASSWORD": "",
        "HOST": "",
        "PORT": "",
    }
}

S3_ENDPOINT_URL = "https://s3.wasabisys.com"
if os.environ.get("S3_ACCESS_KEY"):
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
if os.environ.get("S3_SECRET_KEY"):
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
