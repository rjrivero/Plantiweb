#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required

from .base import with_profile

DEFAULT_HIST_LEN = 10


class HomeView(dict):

    """Prepara la vista raiz"""

    def __init__(self, request):
        super(dict, self).__init__()
        self.add_history(request)

    def add_history(self, request):
        """Actualiza el historico de comandos"""
        history = request.session.setdefault('history', [])
        q = request.GET.get('q', u'')
        h = int(request.GET.get('h', DEFAULT_HIST_LEN))
        h_list = (5, 10, 15, 20, 25)
        if 0 < h <= h_list[-1] and len(history) > h:
            history = history[:h]
        if q:
            try:
                selected = history.index(q)
            except ValueError:
                selected = 0
                history.insert(0, q)
        request.session['history'] = history
        self.update(**locals())
        return q


@login_required
@with_profile
def homeview(request):
    return render_to_response('datanav/home.html',
        HomeView(request),
        context_instance=RequestContext(request))

