#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from django.conf.urls.defaults import *


urlpatterns = patterns('example.views',
    # Example:
    url(r'^home/(?P<attr>\w[\w\d]*)/$', 'nodelist', name='rootview'),
    url(r'^list(?P<path>(/\w[\w\d]*)+)/(?P<id>\d+)/(?P<attr>\w[\w\d]*)/$', 'nodelist', name='listview'),
    url(r'^node(?P<path>(/\w[\w\d]*)+)/(?P<id>\d+)/$', 'node', name='nodeview'),
)
