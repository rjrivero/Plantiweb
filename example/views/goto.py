#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import numbers
from urllib import urlencode

from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django.contrib.auth.decorators import login_required

from .base import with_profile
from ..models import Cache


@login_required
@with_profile
def gotoview(request, parent_pk, parent_instance, child_pk):
    # busco la instancia padre.
    try:
        profile = request.session['profile']
        model = Cache(parent_pk)
        child = Cache(child_pk)
        instance = model.objects.get(pk=parent_instance)
    except (KeyError, IndexError):
        query = ""
    else:
        identities = (profile.identity(x) for x in model._DOMD.path)
        path = []
        for attr in reversed(tuple(identities)):
            path.append((instance._DOMD.name, attr, getattr(instance, attr)))
            instance = instance.up
        path.reverse()
        query = [];
        for name, identity, value in path:
            if not isinstance(value, numbers.Real):
                value = "'%s'" % str(value).encode('string-escape')
            query.append("%s(%s=%s)" % (name, identity, value))
        query.append(child._DOMD.name)
        query = ".".join(query)
    homeurl = "%s?%s" % (reverse('homeview'), urlencode({'q': query}));
    return redirect(homeurl)
