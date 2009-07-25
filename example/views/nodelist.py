#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.http import HttpResponse
from django.core.urlresolvers import reverse

from example.meta import MetaClass
from example.models import *


def nodelist(request, path, id, attr):
    root = MetaClass.data._type
    result = []
    children = []
    try:
        for step in (x for x in path.split("/") if x):
            root = root._Properties[step]._type
        item = root.objects.get(pk=int(id))
        data = getattr(item, attr)
        path = '/'.join((path, attr))
        for item in data:
            url = reverse('example.views.node', kwargs={'path': path, 'id':item.pk})
            result.append("<a href='%s'>%s</a><br/>" % (url, str(item)))
    except (KeyError, AttributeError):
        pass
    return HttpResponse("".join(result))

