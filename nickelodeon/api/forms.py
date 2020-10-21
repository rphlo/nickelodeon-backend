from django.conf import settings
from django.forms import Form
from django.urls import reverse

from resumable.fields import ResumableFileField as OrigResumableFileField

from nickelodeon.api.widgets import ResumableFileInput


class ResumableFileField(OrigResumableFileField):
    widget = ResumableFileInput


class ResumableMp3UploadForm(Form):
    file = ResumableFileField(
        allowed_mimes=("audio/mpeg",),
        upload_url='/mp3-upload',
        chunks_dir=getattr(settings, 'FILE_UPLOAD_TEMP_DIR')
    )
