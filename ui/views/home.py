#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required

from .base import with_profile
from .homecontext import HomeContext


@login_required
@with_profile
def homeview(request):
    hc = HomeContext(request)
    hc.analyze_query(request, hc['q'])
    return render_to_response('datanav/home.html', hc,
        context_instance=RequestContext(request))

