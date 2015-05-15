from rest_framework import serializers
from nickelodeon.models import Song, YouTubeDownloadTask


class RelativeURLField(serializers.ReadOnlyField):
    """
    Field that returns a link to the relative url.
    """
    def to_representation(self, value):
        request = self.context.get('request')
        url = request and request.build_absolute_uri(value) or ''
        return url


class SongSerializer(serializers.ModelSerializer):
    url = RelativeURLField(source='get_absolute_url')
    download_url = RelativeURLField(source='get_download_url')
    availability = serializers.ReadOnlyField(source='available_formats')
    filename = serializers.CharField(required=False)

    def update(self, instance, validated_data):
        has_moved = (validated_data['filename'] != instance.filename)
        original_instance = Song(filename=instance.filename)
        saved_instance = super(SongSerializer, self).update(instance,
                                                            validated_data)
        if has_moved:
            saved_instance.move_file_from(original_instance)
        return saved_instance

    class Meta:
        model = Song
        fields = ('uuid', 'url', 'download_url', 'artist',
                  'title', 'filename', 'availability')


class YouTubeDownloadTaskSerializer(serializers.ModelSerializer):
    task_progress_url = RelativeURLField(source='get_task_url')

    class Meta:
        model = YouTubeDownloadTask
        fields = ('video_id', 'task_progress_url', )
