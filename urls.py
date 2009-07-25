#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

import os.path

from django.conf import settings
from django.conf.urls.defaults import *
from django.views.static import serve

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',
    # Example:
    (r'^example/', include('example.urls')),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^admin/(.*)', admin.site.root),
)

if settings.DEBUG:
    media_dir = os.path.join(os.path.dirname(__file__), 'resources').replace('\\', '/')
    urlpatterns += patterns('',
        (r'^resources/(?P<path>.*)$', serve, {'document_root': media_dir}),
    )
