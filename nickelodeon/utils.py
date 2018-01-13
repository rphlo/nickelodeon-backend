import io
import re
import subprocess


def has_ffmpeg_lib(lib_name):
    process = subprocess.Popen(['ffmpeg'],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               bufsize=10 ** 8)


    process_reader = io.TextIOWrapper(process.stdout, encoding='utf8')
    return '--enable-{}'.format(lib_name) in process_reader.read()


def has_ffmpeg_libmp3lame():
    return has_ffmpeg_lib('libmp3lame')


def has_ffmpeg_libfdk_aac():
    return has_ffmpeg_lib('libfdk-aac')


class FFMPEGTask(object):
    duration = ''
    duration_prefix = 'Duration: '
    duration_prefix_chr_found = 0
    duration_found = False
    progress = ''
    progress_prefix = 'time='
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

    def search_duration_str(self, out):
        if self.duration_prefix_chr_found < len(self.duration_prefix):
            # While the prefix hasn't been found yet
            if out == self.duration_prefix[self.duration_prefix_chr_found]:
                self.duration_prefix_chr_found += 1
            elif out == self.duration_prefix[0]:
                self.duration_prefix_chr_found = 1
            else:
                self.duration_prefix_chr_found = 0
        else:
            # Prefix has been found
            # Read data until comma
            if out in '0123456789:.':
                self.duration += out
            else:
                self.duration_found = True

    def search_progress_str(self, out):
        if self.progress_prefix_chr_found < len(self.progress_prefix):
            if out == self.progress_prefix[self.progress_prefix_chr_found]:
                self.progress_prefix_chr_found += 1
            elif out == self.progress_prefix[0]:
                self.progress_prefix_chr_found = 1
            else:
                self.progress_prefix_chr_found = 0
        else:
            if out in '0123456789:.':
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
            '-b:a', '32k',
            '-c:a', 'libfdk_aac', '-level', '10', '-profile:a', 'aac_he_v2',
            '-movflags', '+faststart', '-cutoff', '20000',
            '-f', 'mp4', output_file_aac,
        ]
    task = FFMPEGTask(command, callback)
    task.run()
    return
