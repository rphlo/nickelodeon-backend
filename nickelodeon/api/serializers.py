import re
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from nickelodeon.models import MP3Song


def validate_filename(filename):
    if re.search(r'[:<>\\"|?*]', filename):
        raise ValidationError('Illegal character found')
    return True


class RelativeURLField(serializers.ReadOnlyField):
    """
    Field that returns a link to the relative url.
    """
    def to_representation(self, value):
        request = self.context.get('request')
        url = request and request.build_absolute_uri(value) or ''
        return url


class MP3SongSerializer(serializers.ModelSerializer):
    url = RelativeURLField(source='get_absolute_url')
    download_url = RelativeURLField(source='get_download_url')
    filename = serializers.CharField(
        required=False,
        validators=[validate_filename]
    )
    id = serializers.ReadOnlyField()

    def update(self, instance, validated_data):
        if not instance.is_filename_available(validated_data['filename']):
            raise ValidationError('Filename already used')
        original_instance = MP3Song(filename=instance.filename)
        saved_instance = super(MP3SongSerializer, self).update(instance,
                                                               validated_data)
        if validated_data['filename'] != original_instance.filename:
            saved_instance.move_file_from(original_instance)
        return saved_instance

    class Meta:
        model = MP3Song
        fields = ('id', 'url', 'filename', 'download_url')
