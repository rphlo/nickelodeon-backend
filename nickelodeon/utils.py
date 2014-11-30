import re
import os
import subprocess
from shutil import copystat
from django.core.files import locks


def _samefile(src, dst):
    # Macintosh, Unix.
    if hasattr(os.path, 'samefile'):
        try:
            return os.path.samefile(src, dst)
        except OSError:
            return False

    # All other platforms: check for same pathname.
    return (os.path.normcase(os.path.abspath(src)) ==
            os.path.normcase(os.path.abspath(dst)))


def file_move_safe(old_file_name, new_file_name, chunk_size=1024 * 64,
                   allow_overwrite=True):
    """
    Moves a file from one location to another in the safest way possible.

    First, tries ``os.rename``, which is simple but will break across
    filesystems.
    If that fails, streams manually from one file to another in pure Python.

    If the destination file exists and ``allow_overwrite`` is ``False``, this
    function will throw an ``IOError``.
    """
    # There's no reason to move if we don't have to.

    if _samefile(old_file_name, new_file_name):
        return

    try:
        # If the destination file exists and allow_overwrite is False then
        # raise an IOError
        if not allow_overwrite and os.access(new_file_name, os.F_OK):
            raise IOError("Destination file %s exists and allow_overwrite is "
                          "False" % new_file_name)

        os.rename(old_file_name, new_file_name)
        return
    except OSError:
        # This will happen with os.rename if moving to another filesystem
        # or when moving opened files on certain operating systems
        pass

    # first open the old file, so that it won't go away
    with open(old_file_name, 'rb') as old_file:
        # now open the new file, not forgetting allow_overwrite
        fd = os.open(new_file_name,
                     (os.O_WRONLY | os.O_CREAT | getattr(os, 'O_BINARY', 0)
                      | (os.O_EXCL if not allow_overwrite else 0)))
        try:
            locks.lock(fd, locks.LOCK_EX)
            current_chunk = None
            while current_chunk != b'':
                current_chunk = old_file.read(chunk_size)
                os.write(fd, current_chunk)
        finally:
            locks.unlock(fd)
            os.close(fd)
    try:
        copystat(old_file_name, new_file_name)
    except OSError:
        pass
    try:
        os.remove(old_file_name)
    except OSError as e:
        # Certain operating systems (Cygwin and Windows)
        # fail when deleting opened files, ignore it.  (For the
        # systems where this happens, temporary files will be auto-deleted
        # on close anyway.)
        if getattr(e, 'winerror', 0) != 32 and getattr(e, 'errno', 0) != 13:
            raise


class FFmpegTask(object):
    duration = ''
    duration_prefix = 'Duration: '
    duration_prefix_chr_found = 0
    duration_found = False
    progress = ''
    progress_prefix = 'time='
    progress_prefix_chr_found = 0
    process = None
    process_completed = False

    def __init__(self, command, callback=None):
        self.command = command
        self.callback = callback

    def run(self):
        self.process = subprocess.Popen(self.command,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,
                                        bufsize=10**8)
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
        out = self.process.stdout.read(1)
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
    task = FFmpegTask(command, callback)
    task.run()
    return
