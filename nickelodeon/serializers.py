from rest_framework import serializers
from .models import Song
from rest_framework.templatetags.rest_framework import replace_query_param


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
    availability = serializers.Field('available_formats')
    filename = serializers.Field()

    class Meta:
        model = Song
        fields = ('uuid', 'url', 'artist', 'title', 'filename', 'availability')