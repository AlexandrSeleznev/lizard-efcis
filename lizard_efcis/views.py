# (c) Nelen & Schuurmans.  GPL licensed, see LICENSE.rst.
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from __future__ import print_function

from django.utils.translation import ugettext as _

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from rest_framework.reverse import reverse

from lizard_efcis import models
from lizard_efcis import serializers
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage


def get_filtered_opnames(queryset, request):

    location = request.QUERY_PARAMS.get('locatie')
    if location not in [None, '']:
        queryset = queryset.filter(locatie__loc_id__iexact=location)
    
    return queryset


@api_view()
def api_root(request, format=None):
    return Response({
        'opnames': reverse(
            'opname-list',
            request-request,
            format=format),
    })


@api_view(['GET'])
def opname_list(request):

    ITEMS_PER_PAGE = 30

    if request.method == 'GET':

        page = request.QUERY_PARAMS.get('page')
        page_size = request.QUERY_PARAMS.get('page_size')
        if page_size not in [None, '']:
            ITEMS_PER_PAGE = page_size
        queryset = get_filtered_opnames(
            models.Opname.objects.all(),
            request)

        paginator = Paginator(queryset, ITEMS_PER_PAGE)
        try:
            opnames = paginator.page(page)
        except PageNotAnInteger:
            opnames = paginator.page(1)
        except EmptyPage:
            opnames = paginator.page(paginator.num_pages)

        serializer = serializers.PaginatedOpnameSerializer(
            opnames,
            context={'request': request})
        return Response(serializer.data)
    else:
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)
