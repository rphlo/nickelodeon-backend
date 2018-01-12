import base64
import os.path
import tempfile
from django.contrib.auth.models import User
from django.test import override_settings
from django.urls import reverse
from nickelodeon.models import MP3Song
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

PATH_TEMP = tempfile.mkdtemp()


class ApiTestCase(APITestCase):
    def setUp(self):
        self.username = 'alice'
        self.email = 'alice@aol.com'
        self.password = 'passw0rd!'
        self.user = User.objects.create_user(
            self.username,
            self.email,
            self.password,
        )
        self.client = APIClient()
        self.create_mp3()

    def create_mp3(self):
        mp3_base64 = '''/+MYxAAAAANIAAAAAExBTUUzLjk4LjIAAAAAAAAAAAAAAAAAAAAAA
                        AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'''
        with  open(os.path.join(PATH_TEMP, 'foo.mp3'), 'wb') as fh:
            fh.write(base64.b64decode(mp3_base64))
        self.song = MP3Song.objects.create(
            filename='foo'
        )

    def test_authorization(self):
        url = reverse('knox_login')
        res = self.client.post(url,
                               data={'username': self.username,
                                     'password': self.password})
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(res.data.get('token'))

    def test_auth_wrong_password(self):
        url = reverse('knox_login')
        res = self.client.post(url,
                          data={'username': self.username,
                                'password': 'wrong_password'})
        self.assertEquals(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEquals(res.data.get('non_field_errors'),
                          ['Unable to log in with provided credentials.'])

    def test_auth_wrong_username(self):
        url = reverse('knox_login')
        res = self.client.post(url,
                               data={'username': 'wrong_username',
                                     'password': self.password})
        self.assertEquals(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEquals(res.data.get('non_field_errors'),
                          ['Unable to log in with provided credentials.'])

    @override_settings(NICKELODEON_MUSIC_ROOT=PATH_TEMP)
    def test_api(self):
        login_url = reverse('knox_login')
        res = self.client.post(login_url,
                               data={'username': self.username,
                                     'password': self.password})
        auth_token = res.data.get('token')
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + auth_token)
        random_song_url = reverse('song_random')
        res = self.client.get(random_song_url)
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        expected = {
            'filename': 'foo',
            'url': ('http://testserver' +
                    reverse('song_detail',
                            kwargs={'pk': self.song.id})),
            'download_url': ('http://testserver' +
                             reverse('song_download',
                                     kwargs={'pk': self.song.id})),
            'id': self.song.id
        }
        self.assertEquals(res.data, expected)
        song_url = reverse('song_detail', kwargs={'pk': self.song.id})
        res=self.client.get(song_url)
        self.assertEquals(res.data, expected)
        download_url = reverse('song_download', kwargs={'pk': self.song.id})
        res = self.client.get(download_url)
        self.assertEquals(res.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEquals(res.get('X-Accel-Redirect'), '/internal/foo.mp3')
        res = self.client.put(song_url, data={'filename': 'bar'})
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        expected['filename'] = 'bar'
        self.assertEquals(res.data, expected)
        self.assertTrue(os.path.exists(os.path.join(PATH_TEMP, 'bar.mp3')))
        res = self.client.get(download_url)
        self.assertEquals(res.status_code, status.HTTP_206_PARTIAL_CONTENT)
        self.assertEquals(res.get('X-Accel-Redirect'), '/internal/bar.mp3')
        res = self.client.delete(song_url)
        self.assertEquals(res.status_code, status.HTTP_204_NO_CONTENT)
        res = self.client.get(random_song_url)
        self.assertEquals(res.status_code, status.HTTP_404_NOT_FOUND)
        res = self.client.get(song_url)
        self.assertEquals(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(os.path.exists(os.path.join(PATH_TEMP, 'bar.mp3')))
        self.create_mp3()
        search_url = reverse('song_list')
        res = self.client.get(search_url, data={'q': 'foo'})
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertEquals(len(res.data), 1)
        res = self.client.get(search_url, data={'q': ''})
        self.assertEquals(res.status_code, status.HTTP_200_OK)
        self.assertEquals(len(res.data), 0)
        logout_url = reverse('knox_logout')
        res = self.client.post(logout_url)
        self.assertEquals(res.status_code, status.HTTP_204_NO_CONTENT)