from .settings import *  # noqa: F403, F401

try:
    from .local_settings import *  # noqa: F403, F401
except ImportError:
    pass

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

S3_ENDPOINT_URL = "http://localhost:9000"
S3_ACCESS_KEY = "minioadmin"
S3_SECRET_KEY = "minioadmin"
