#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from django.conf.urls.defaults import *
from django.contrib.auth import views
from django.contrib.auth.decorators import login_required


urlpatterns = patterns('ui.views',
    # Autenticacion
    url(r'^login/$', views.login, name='loginview'),
    url(r'^logout/$', views.logout_then_login, name='logoutview'),
    url(r'^chpass/$', views.password_change,
                      {'post_change_redirect': '../chdone/'},
                      name='chpassview'),
    url(r'^chdone/$', login_required(views.password_change_done),
                      name='chdoneview'),
)

urlpatterns = urlpatterns + patterns('ui.views',
    # Navegacion
    url(r'^home/$', 'homeview', name='homeview'),
    url(r'^grid/(?P<pk>\d+)/$', 'gridview', name='gridview'),
    url(r'^help/(?P<pk>\d+)/$', 'helpview', name='helpview'),
    url(r'^add/(?P<pk>\d+)/$', 'addview', name='addview'),
    url(r'^goto/(?P<parent_pk>\d+)/(?P<parent_instance>\d+)/(?P<child_pk>\d+)/$', 'gotoview', name='gotoview'),
    #url(r'^home/(?P<attr>\w[\w\d]*)/$', 'nodelist', name='rootview'),
    #url(r'^list(?P<path>(/\w[\w\d]*)+)/(?P<id>\d+)/(?P<attr>\w[\w\d]*)/$',
    #       'nodelist', name='listview'),
    #url(r'^node(?P<path>(/\w[\w\d]*)+)/(?P<id>\d+)/$', 'node',
    #       name='nodeview'),
)

