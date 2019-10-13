import re

from django.contrib.auth.models import User

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
    owner = serializers.ReadOnlyField(source='owner__username')
    id = serializers.ReadOnlyField()
    aac = serializers.ReadOnlyField()

    def update(self, instance, validated_data):
        if not instance.is_filename_available(validated_data['filename'], instance.owner):
            raise ValidationError('Filename already used')
        original_instance = MP3Song(
            filename=instance.filename,
            owner=instance.owner
        )
        saved_instance = super(MP3SongSerializer, self) \
            .update(instance, validated_data)
        if validated_data['filename'] != original_instance.filename:
            saved_instance.move_file_from(original_instance)
        return saved_instance

    class Meta:
        model = MP3Song
        fields = ('id', 'url', 'filename', 'download_url', 'aac', 'owner')


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        style={
            'input_type': 'password',
            'placeholder': 'Old Password'
        }
    )
    new_password = serializers.CharField(
        style={
            'input_type': 'password',
            'placeholder': 'New Password'
        }
    )
    confirm_password = serializers.CharField(
        style={
            'input_type': 'password',
            'placeholder': 'Confirm New Password'
        }
    )

    def validate_new_password(self, value):
        # TODO: Check password strength
        return value

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError(
                'Confirmation of new password did not match'
            )
        return data

    def create(self, validated_data):
        return validated_data.get('new_password')

