import re
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, StreamingHttpResponse
from django.conf import settings
from django.db.models import Q
from django.contrib.auth.decorators import permission_required
from rest_framework.generics import (ListAPIView, RetrieveUpdateAPIView,
                                     ListCreateAPIView)
from rest_framework.response import Response
from common_base.social.decorators import api_key_authentication

from nickelodeon.serializers import (SongSerializer,
                                     YouTubeDownloadTaskSerializer)
from nickelodeon.models import Song, YouTubeDownloadTask


def x_accel_redirect(request, path, filename='',
                     mime="application/force-download"):
    if settings.DEBUG:
        from django.core.servers.basehttp import FileWrapper
        import os.path
        path = re.sub(r'^/internal', settings.MEDIA_ROOT, path)
        wrapper = FileWrapper(file(path))
        response = StreamingHttpResponse(wrapper, content_type=mime)
        response['Content-Length'] = os.path.getsize(path)
        response['Content-Type'] = mime
    else:
        response = HttpResponse('', status=206)
        response['X-Accel-Redirect'] = path.encode('utf-8')
        response['Content-Type'] = mime
    response['Content-Disposition'] = "attachment; filename=%s" % filename
    response['Accept-Ranges'] = 'bytes'
    response['X-Accel-Buffering'] = 'no'
    return response


@api_key_authentication()
@permission_required('nickelodeon.can_listen_song')
def download_song(request, pk, extension=None):
    song = get_object_or_404(Song, pk=pk)
    file_path = song.filename
    if extension is None:
        for ext in ('aac', 'mp3'):
            if song.file_format_available(ext):
                extension = ext
    if extension is None or not song.file_format_available(extension):
        return HttpResponse(status=404)
    mime = 'audio/mpeg' if extension == 'mp3' else 'audio/x-m4a'
    file_path = u'{}.{}'.format(file_path, extension)
    file_path = u"/internal{}".format(file_path)
    return x_accel_redirect(request, file_path, mime=mime)


class YouTubeDownloadApiView(ListCreateAPIView):
    """
    Download YouTube Video API
    q -- Search terms (Default: '')
    page -- Page number (Default: 1)
    results_per_page -- Number of result per page (Default:20 Max: 1000)
    """
    model = YouTubeDownloadTask
    serializer_class = YouTubeDownloadTaskSerializer

    def __init__(self):
        self.paginate_by = 20
        self.paginate_by_param = 'results_per_page'
        self.max_paginate_by = 1000
        super(YouTubeDownloadApiView, self).__init__()

    def list(self, request, *args, **kwargs):
        video_id = request.QUERY_PARAMS.get('v', '').strip()
        if video_id:
            object_list = self.model.objects.filter(video_id=video_id)
        else:
            object_list = self.model.objects.all()
        page = self.paginate_queryset(object_list)
        if page is not None:
            serializer = self.get_pagination_serializer(page)
        else:
            serializer = self.get_serializer(object_list, many=True)
        return Response(serializer.data)


class SongView(RetrieveUpdateAPIView):
    model = Song
    serializer_class = SongSerializer


class TextSearchApiView(ListAPIView):
    """
    Search Songs API
    q -- Search terms (Default: '')
    page -- Page number (Default: 1)
    results_per_page -- Number of result per page (Default:20 Max: 1000)
    """
    model = Song
    serializer_class = SongSerializer
    lookup_fields = ('filename', 'artist', 'title')

    def __init__(self):
        self.paginate_by = 20
        self.paginate_by_param = 'results_per_page'
        self.max_paginate_by = 1000
        super(TextSearchApiView, self).__init__()

    def list(self, request, *args, **kwargs):
        search_text = request.QUERY_PARAMS.get('q', '').strip()
        if search_text:
            search_terms = search_text.split(' ')
            query = Q()
            for search_term in search_terms:
                sub_query = Q()
                for field_name in self.lookup_fields:
                    kwargs = {}
                    kwargs['%s__icontains' % field_name] = search_term
                    sub_query |= Q(**kwargs)
                query &= sub_query
            object_list = self.model.objects.filter(query)
        else:
            object_list = self.model.objects.all()
        object_list = object_list.order_by('title', 'artist')
        page = self.paginate_queryset(object_list)
        if page is not None:
            serializer = self.get_pagination_serializer(page)
        else:
            serializer = self.get_serializer(object_list, many=True)
        return Response(serializer.data)
