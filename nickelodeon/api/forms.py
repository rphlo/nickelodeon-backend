from django.conf import settings
from django.forms import Form

from resumable.fields import ResumableFileField


class ResumableMp3UploadForm(Form):
    file = ResumableFileField(
        allowed_mimes=("audio/mpeg",),
        upload_url='/mp3-upload',
        chunks_dir=getattr(settings, 'FILE_UPLOAD_TEMP_DIR')
    )
