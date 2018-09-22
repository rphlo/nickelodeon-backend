import base64
import io
import os
import random
import re
import struct
import subprocess


AVAILABLE_FORMATS = {'mp3': 'libmp3lame', 'aac': 'libfdk-aac'}
FFMPEG_DURATION_PREFIX = 'Duration: '
FFMPEG_PROGRESS_PREFIX = 'time='
VALID_TIME_STR_CHARS = '0123456789:.'


def clean_empty_folder(folder):
    while not os.listdir(folder):
        os.rmdir(folder)
        folder = os.path.dirname(folder)


def random_key():
    rand_bytes = bytes(struct.pack('Q', random.getrandbits(64)))
    b64 = base64.b64encode(rand_bytes).decode('utf-8')
    b64 = b64[:11]
    b64 = b64.replace('+', '-')
    b64 = b64.replace('/', '_')
    return b64


def ffmpeg_has_lib(lib_name):
    process = subprocess.Popen(['ffmpeg'],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               bufsize=10 ** 8)


    process_reader = io.TextIOWrapper(process.stdout, encoding='utf8')
    return '--enable-{}'.format(lib_name) in process_reader.read()


class FFMPEGTask(object):
    duration = ''
    duration_prefix_chr_found = 0
    duration_found = False
    progress = ''
    progress_prefix_chr_found = 0
    process = None
    process_completed = False
    process_reader = None

    def __init__(self, command, callback=None):
        self.command = command
        self.callback = callback

    def run(self):
        self.process = subprocess.Popen(self.command,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        bufsize=10**8)
        self.process_reader = io.TextIOWrapper(self.process.stdout,
                                               encoding='utf8')
        while not self.process_completed:
            self.track_progress()

    @staticmethod
    def parse_time_str(time_str):
        if not re.match('\d+:\d{2}:\d{2}\.\d+', time_str):
            return 0
        hours, minutes, seconds = [float(x) for x in time_str.split(':')]
        return (hours*60+minutes)*60+seconds

    def search_time_str(self, out, prefix, prefix_char_found):
        if prefix_char_found < len(prefix):
            if out == prefix[prefix_char_found]:
                prefix_char_found += 1
            elif out == prefix[0]:
                prefix_char_found = 1
            else:
                prefix_char_found = 0
            return prefix_char_found
        return -1

    def search_duration_str(self, out):
        self.duration_prefix_chr_found = self.search_time_str(
            out,
            FFMPEG_DURATION_PREFIX,
            self.duration_prefix_chr_found,
        )
        if self.duration_prefix_chr_found == -1 or len(self.duration) > 0:
            # Prefix has been found
            # Read data until comma
            if out in VALID_TIME_STR_CHARS:
                self.duration += out
            else:
                self.duration_found = True

    def search_progress_str(self, out):
        self.progress_prefix_chr_found = self.search_time_str(
            out,
            FFMPEG_PROGRESS_PREFIX,
            self.progress_prefix_chr_found
        )
        if self.progress_prefix_chr_found == -1 or len(self.progress) > 0:
            if out in VALID_TIME_STR_CHARS:
                self.progress += out
            else:
                if self.callback:
                    prog_sec = self.parse_time_str(self.progress)
                    dura_sec = self.parse_time_str(self.duration)
                    percent = min(1, prog_sec/dura_sec)
                    self.callback(percent)
                self.progress = ''
                self.progress_prefix_chr_found = 0

    def track_progress(self):
        out = self.process_reader.read(1)
        if out == '' and self.process.poll() is not None:
            self.process_completed = True
        if out != '':
            if not self.duration_found:
                self.search_duration_str(out)
            self.search_progress_str(out)


def convert_audio(input_file, output_file_aac=None, output_file_mp3=None,
                  callback=None):
    command = ['ffmpeg', '-y', '-i', input_file, '-threads', '0', '-vn']
    if output_file_mp3 is not None:
        command += [
            '-ar', '44100', '-ac', '2',
            '-b:a', '192k',
            '-f', 'mp3', output_file_mp3,
        ]
    if output_file_aac is not None:
        command += [
            '-ar', '44100', '-ac', '2',
            '-b:a', '64k', '-c:a', 'aac',
            '-movflags', '+faststart',
            '-f', 'mp4', output_file_aac,
        ]
    task = FFMPEGTask(command, callback)
    task.run()
    return


if __name__ == '__main__':
    convert_audio(
        '/tmp/test_input.mp3',
        '/tmp/test_aac_out.aac',
        '/tmp/test_mp3_out.mp3',
        lambda x: print(x)
    )
