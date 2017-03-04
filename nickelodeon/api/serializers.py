from rest_framework import serializers
from nickelodeon.models import MP3Song


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
    filename = serializers.CharField(required=False)
    id = serializers.ReadOnlyField()

    def update(self, instance, validated_data):
        has_moved = (validated_data['filename'] != instance.filename)
        original_instance = MP3Song(filename=instance.filename)
        saved_instance = super(MP3SongSerializer, self).update(instance,
                                                            validated_data)
        if has_moved:
            saved_instance.move_file_from(original_instance)
        return saved_instance

    class Meta:
        model = MP3Song
        fields = ('id', 'url', 'download_url', 'filename', 'has_aac')