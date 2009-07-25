#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from django.conf.urls.defaults import *


urlpatterns = patterns('example.views',
    # Example:
    (r'^home/?$', 'home'),
    (r'^list(?P<path>(/\w[\w\d]*)+)/(?P<id>\d+)/(?P<attr>\w[\w\d]*)/?$', 'nodelist'),
    (r'^node(?P<path>(/\w[\w\d]*)+)/(?P<id>\d+)/?$', 'node'),
)
