import re
import random
import anyjson as json
from urllib import unquote as url_unquote

from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.http import HttpResponse, StreamingHttpResponse
from django.conf import settings
from django.db.models import Q

from rest_framework.generics import ListAPIView, RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.renderers import (BaseRenderer, JSONRenderer)

from .serializers import SongSerializer
from .tasks import fetch_youtube_video_infos
from .models import Song


class XAccelRedirectRenderer(BaseRenderer):
    media_type = 'application/force-download'
    format = 'bin'
    path_field = 'filename'
    charset = None
    render_style = 'binary'

    def x_accel_redirect(self, path, filename=None,
                         mime="application/force-download"):
        if settings.DEBUG and True:
            from django.core.servers.basehttp import FileWrapper
            import re
            import os.path
            path = re.sub(r'^/internal', settings.MEDIA_ROOT, path)
            wrapper = FileWrapper(file(path))
            response = StreamingHttpResponse(wrapper, content_type=mime)
            response['Content-Length'] = os.path.getsize(path)
            response['Content-Type'] = mime
            return response
        response = HttpResponse(path)
        response['Content-Type'] = mime
        response['X-Accel-Redirect'] = path
        return response

    def extract_path(self, data):
        if data is None:
            return ''
        if not isinstance(data, dict):
            return ''
        file_path = data.get(self.path_field)
        return "/internal%s" % file_path

    def render(self, data, accepted_media_type=None, renderer_context=None):
        file_path = self.extract_path(data)
        return self.x_accel_redirect(file_path, mime=self.media_type)


class Mp3Renderer(XAccelRedirectRenderer):
    media_type = 'audio/mpeg'
    format = 'mp3'
    path_field = 'filename'


class AacRenderer(Mp3Renderer):
    media_type = 'audio/aac'
    format = 'aac'
    path_field = 'filename'

    def extract_path(self, data):
        mp3_filename = super(AacRenderer,self).extract_path(data)
        return re.sub(r'(mp3$)', 'aac', mp3_filename)


class SongView(RetrieveUpdateAPIView):
    model = Song
    serializer_class = SongSerializer

    def __init__(self):
        if Mp3Renderer not in self.renderer_classes:
            self.renderer_classes.append(Mp3Renderer)
            self.renderer_classes.append(AacRenderer)
            super(SongView, self).__init__()


class TextSearchApiView(ListAPIView):
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
        try:
            offset = int(request.QUERY_PARAMS.get('offset', 0))
        except (TypeError, ValueError):
            offset = 0
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
            print query
            object_list = self.model.objects.filter(query)
        else:
            object_list = self.model.objects.all()
        object_list = object_list.order_by('title', 'artist')
        if offset > 0:
            object_list = object_list[offset:]
        page = self.paginate_queryset(object_list)
        if page is not None:
            serializer = self.get_pagination_serializer(page)
        else:
            serializer = self.get_serializer(object_list, many=True)
        return Response(serializer.data)


def import_from_youtube_url(request):
    task = fetch_youtube_video_infos.s().delay()
    task_id = str(task.task_id)
    return HttpResponse(task_id)
