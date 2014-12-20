#! /usr/bin/env python
import re
import requests
from urlparse import urljoin
from urllib import unquote


ZIPPYSHARE_URL_RE = re.compile(r'(?P<HOST>http://www\d{0,2}\.zippyshare\.com)'
                               r'/v(?:/|iew\.jsp.*key=)(?P<KEY>\d+)')


class ZippyshareHelper(object):
    session = None
    orig_url = None
    file_name = None
    download_url = None
    self.title = None

    def __init__(self, url):
        self.session = requests.Session()
        self.orig_url = url

    def retrieve_details(self):
        url_match = ZIPPYSHARE_URL_RE.match(self.orig_url)
        if not url_match:
            raise ValueError('Not a valid zippyshare url')
        host = url_match.group('HOST')
        key = url_match.group('KEY')
        self.file_name, checksum = self.get_name_and_checksum()
        self.title = unquote(self.file_name[:-4])
        p_url = '/'.join(("d", key, str(checksum), self.file_name))
        self.download_url = urljoin(host, p_url)

    def get_name_and_checksum(self):
        try:
            resp = self.session.get(self.orig_url)
            html = resp.text
        except requests.exceptions.ConnectionError:
            raise ValueError("Unable to retrieve page")
        try:
            name = re.search(
                r'\"/d.*\/(?P<file_name>[^\/]+\.mp3)\"',
                html
            ).group('file_name')
            m = re.search(r'\+[ ]*\((\d+)[ ]*\%[ ]*(\d+)'
                          r'[ ]*\+[ ]*(\d+)[ ]*\%[ ]*(\d+)\)[ ]*\+', html)
            if m:
                a1, a2, c1, c2 = map(int, m.groups())
            else:
                a1, a2 = map(
                    int,
                    re.search(
                        r'\(\'downloadB\'\).omg = (\d+)%(\d+)',
                        html
                    ).groups()
                )
                c1, c2 = map(
                    int,
                    re.search(
                        r'\(\'downloadB\'\).omg\) \* \((\d+)%(\d+)',
                        html
                    ).groups()
                )
            b = (a1 % a2) * (c1 % c2)
        except:
            raise ValueError("Unable to calculate checksum")
        else:
            return name, (b + 18)

    def download(self, download_path=None, callback=None, quiet=False):
        if not self.download_url:
            return
        if download_path is None:
            download_path = unquote(self.file_name)
        with open(download_path, 'wb') as fp:
            response = self.session.get(self.download_url, stream=True)
            bytes_downloaded = 0
            bytes_total = int(response.headers['content-length'])
            for chunk in response.iter_content(chunk_size=32*1024):
                if chunk:
                    fp.write(chunk)
                    fp.flush()
                    bytes_downloaded += len(chunk)
                    if not quiet:
                        print "%.2f" % bytes_downloaded/bytes_total*100
                    if callback:
                        callback(float(bytes_downloaded)/bytes_total)


if __name__ == '__main__':
    import sys
    if len(sys.argv) <= 1:
        exit()
    for url in sys.argv[1:]:
        media = ZippyshareHelper(url)
        media.retrieve_details()
        media.download()
