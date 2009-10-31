#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required

from ..models import Cache
from .base import with_profile
from .editcontext import EditContext


@login_required
@with_profile
def addview(request, pk):
    context = EditContext(request, int(pk))
    context['pk'] = context['model_pk']
    return render_to_response('datanav/add.html', context,
        context_instance=RequestContext(request))
