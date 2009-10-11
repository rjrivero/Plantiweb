#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required

from .base import with_profile
from ..models import Cache


@login_required
@with_profile
def helpview(request, pk=None):
    data = dict()
    if pk is not None:
        try:
            model = Cache(int(pk))
        except (TypeError, KeyError):
            pass
        else:
            domd = model._DOMD
            data['help'] = domd.comment or u""
            data['fullname'] = unicode(domd.fullname)
            profile = request.session['profile']
            fields = profile.fields(model, tuple())
            data['fields'] = tuple((x, domd.comments[x]) for x in fields) 
    return render_to_response('datanav/help.html', data,
        context_instance=RequestContext(request))
