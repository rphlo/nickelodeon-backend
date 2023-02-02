import base64
from io import BytesIO
import os.path
import tempfile

from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from nickelodeon.models import MP3Song
from nickelodeon.utils import s3_create_bucket, s3_object_exists, s3_upload

PATH_TEMP = tempfile.mkdtemp()


class ApiTestCase(APITestCase):
    def setUp(self):
        self.username = "alice"
        self.email = "alice@aol.com"
        self.password = "passw0rd!"
        self.user = User.objects.create_user(
            self.username,
            self.email,
            self.password,
        )
        self.user.save()
        self.client = APIClient()
        s3_create_bucket(settings.S3_BUCKET)
        self.create_mp3()

    def create_mp3(self):
        mp3_base64 = (
            "/+MYxAAAAANIAAAAAExBTUUzLjk4LjIAAAAAAAAAAAAAAAAAAAAAA"
            "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        )
        tmp_file = BytesIO(base64.b64decode(mp3_base64))
        s3_upload(tmp_file, f"{self.user.settings.storage_prefix}/foo.mp3")
        self.song = MP3Song.objects.create(owner=self.user, filename="foo")

    def test_authorization(self):
        url = reverse("knox_login")
        res = self.client.post(
            url, data={"username": self.username, "password": self.password}
        )
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(res.data.get("token"))

    def test_auth_wrong_password(self):
        url = reverse("knox_login")
        res = self.client.post(
            url, data={"username": self.username, "password": "wrong_password"}
        )
        self.assertEquals(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEquals(
            res.data.get("non_field_errors"),
            ["Unable to log in with provided credentials."],
        )

    def test_auth_wrong_username(self):
        url = reverse("knox_login")
        res = self.client.post(
            url, data={"username": "wrong_username", "password": self.password}
        )
        self.assertEquals(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEquals(
            res.data.get("non_field_errors"),
            ["Unable to log in with provided credentials."],
        )

    def test_password_change(self):
        view_url = reverse("account_change_password")
        self.client.login(username=self.username, password=self.password)
        res = self.client.put(
            view_url,
            data={
                "old_password": self.password,
                "new_password": "abc_123",
                "confirm_password": "abc_12",
            },
        )
        self.assertEquals(res.status_code, status.HTTP_400_BAD_REQUEST)
        res = self.client.put(
            view_url,
            data={
                "old_password": "wrong password",
                "new_password": "abc_123",
                "confirm_password": "abc_123",
            },
        )
        self.assertEquals(res.status_code, status.HTTP_400_BAD_REQUEST)
        res = self.client.put(
            view_url,
            data={
                "old_password": self.password,
                "new_password": "abc_123",
                "confirm_password": "abc_123",
            },
        )
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.client.logout()
        self.assertTrue(self.client.login(username=self.username, password="abc_123"))
        self.client.logout()
        self.user.set_password(self.password)
        self.user.save()

    def test_api(self):
        login_url = reverse("knox_login")
        res = self.client.post(
            login_url, data={"username": self.username, "password": self.password}
        )
        auth_token = res.data.get("token")
        download_url = reverse(
            "song_download", kwargs={"pk": self.song.id, "extension": "mp3"}
        )
        res = self.client.get(download_url, data={"auth_token": auth_token})
        self.assertEquals(res.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertTrue(
            res.get("X-Accel-Redirect").startswith(
                f"/s3_proxy/{settings.S3_BUCKET}/{self.user.settings.storage_prefix}/foo.mp3"
            )
        )
        self.client.credentials(HTTP_AUTHORIZATION="Token " + auth_token)
        random_song_url = reverse("song_random")
        res = self.client.get(random_song_url)
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        expected = {
            "filename": "foo",
            "url": (
                "http://testserver"
                + reverse("song_detail", kwargs={"pk": self.song.id})
            ),
            "download_url": (
                "http://testserver"
                + reverse("song_download", kwargs={"pk": self.song.id})
            ),
            "id": self.song.id,
            "aac": False,
            "owner": self.username,
        }
        self.assertEquals(res.data, expected)
        song_url = reverse("song_detail", kwargs={"pk": self.song.id})
        res = self.client.get(song_url)
        self.assertEquals(res.data, expected)
        self.assertTrue(
            s3_object_exists(f"{self.user.settings.storage_prefix}/foo.mp3")
        )
        res = self.client.put(song_url, data={"filename": "bar"})
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        expected["filename"] = "bar"
        self.assertEquals(res.data, expected)
        self.assertTrue(
            s3_object_exists(f"{self.user.settings.storage_prefix}/bar.mp3")
        )
        self.assertFalse(
            s3_object_exists(f"{self.user.settings.storage_prefix}/foo.mp3")
        )
        res = self.client.get(download_url)
        self.assertEquals(res.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertTrue(
            res.get("X-Accel-Redirect").startswith(
                f"/s3_proxy/{settings.S3_BUCKET}/{self.user.settings.storage_prefix}/bar.mp3"
            )
        )
        res = self.client.delete(song_url)
        self.assertEquals(res.status_code, status.HTTP_204_NO_CONTENT)
        res = self.client.get(random_song_url)
        self.assertEquals(res.status_code, status.HTTP_404_NOT_FOUND)
        res = self.client.get(song_url)
        self.assertEquals(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(
            s3_object_exists(f"{self.user.settings.storage_prefix}/bar.mp3")
        )
        self.create_mp3()
        search_url = reverse("song_list")
        res = self.client.get(search_url, data={"q": "foo"})
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertEquals(len(res.data), 1)
        res = self.client.get(search_url, data={"q": ""})
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertEquals(len(res.data), 0)
        logout_url = reverse("knox_logout")
        res = self.client.post(logout_url)
        self.assertEquals(res.status_code, status.HTTP_204_NO_CONTENT)
