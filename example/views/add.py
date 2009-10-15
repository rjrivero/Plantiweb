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
def addview(request, pk):
    data = {'pk': pk}
    try:
        model = Cache(int(pk))
    except (TypeError, KeyError):
        pass
    else:
        profile = request.session['profile']
        data['fullname'] = model._DOMD.fullname
        form_type = profile.form(model)
        if form_type:
            if request.POST.get('do', None):
                form = form_type(request.POST)
                if form.is_valid():
                    print "Forma valida!"
            else:
                form = form_type()
            data['form'] = form
    return render_to_response('datanav/add.html', data,
        context_instance=RequestContext(request))
