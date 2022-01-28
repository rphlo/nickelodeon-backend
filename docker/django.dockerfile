FROM python:3.10-bullseye

# Copy in your requirements file
ADD requirements.txt /requirements.txt

# OR, if you’re using a directory for your requirements, copy everything (comment out the above and uncomment this if so):
# ADD requirements /requirements

# Install build deps, then run `pip install`, then remove unneeded build deps all in a single step. Correct the path to your production requirements file, if needed.
RUN set -ex \
    && python -m venv /venv \
    && /venv/bin/pip install -U pip \
    && /venv/bin/pip install -r /requirements.txt

RUN apt-get update
RUN apt-get -y install ffmpeg

# Copy your application code to the container (make sure you create a .dockerignore file if any large files or directories should be excluded)
RUN mkdir /app/
WORKDIR /app/
ADD . /app/

# uWSGI will listen on this port
EXPOSE 8000

# Add any custom, static environment variables needed by Django or your settings file here:
ENV DJANGO_SETTINGS_MODULE=nickelodeon.site.settings

# uWSGI configuration (customize as needed):
# ENV UWSGI_VIRTUALENV=/venv UWSGI_WSGI_FILE=routechoices/wsgi.py UWSGI_HTTP=:8000 UWSGI_MASTER=1 UWSGI_WORKERS=2 UWSGI_THREADS=8 UWSGI_UID=1000 UWSGI_GID=2000 UWSGI_LAZY_APPS=1 UWSGI_WSGI_ENV_BEHAVIOR=holy

# Call collectstatic (customize the following line with the minimal environment variables needed for manage.py to run):
RUN DATABASE_URL=none /venv/bin/python manage.py collectstatic --noinput

# ENTRYPOINT ["/app/docker-entrypoint.sh"]
# Start uWSGI
# CMD ["/venv/bin/uwsgi", "--http-auto-chunked", "--http-keepalive"]

ADD docker/wait-for-it.sh /wait-for-it.sh
ADD docker/run-django.sh /run.sh
RUN chmod 755 /wait-for-it.sh /run.sh
ENTRYPOINT ["/run.sh"]
