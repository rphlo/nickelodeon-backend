from rest_framework import serializers
from .models import Song
from rest_framework.templatetags.rest_framework import replace_query_param
from rest_framework.compat import get_concrete_model

class RelativeURLField(serializers.Field):
    """
    Field that returns a link to the relative url.
    """
    url_field = 'get_absolute_url'

    def to_native(self, value):
        request = self.context.get('request')
        url = request and request.build_absolute_uri(value) or ''
        return url


class SongSerializer(serializers.ModelSerializer):
    url = RelativeURLField('get_absolute_url')
    download_url = RelativeURLField('get_download_url')
    availability = serializers.Field('available_formats')
    filename = serializers.WritableField(required=False)

    def save_object(self, obj, **kwargs):
        if obj.pk is not None:
            orig = Song.objects.get(pk=obj.pk)
            if orig.filename != obj.filename:
                obj.move_file_from(orig)
        super(SongSerializer, self).save_object(obj, **kwargs)

    class Meta:
        model = Song
        fields = ('uuid', 'url', 'download_url', 'artist',
                  'title', 'filename', 'availability')
