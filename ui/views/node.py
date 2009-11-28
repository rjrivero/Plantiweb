#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.http import HttpResponse
from django.core.urlresolvers import reverse

from ui.models import *


def node(request, path, id):
    root = MetaClass.data._type
    result = []
    children = []
    try:
        for step in (x for x in path.split("/") if x):
            root = root._Properties[step]._type
        item = root.objects.get(pk=int(id))
        for name, val in item.iteritems():
            try:
                subtype = item._type._Properties[name]._type
            except (KeyError, AttributeError):
                result.append("%s = %s<br/>" % (name, val))
        for name, value in item._type._Properties.iteritems():
            try:
                subtype = value._type
                url = reverse('ui.views.nodelist', kwargs={'path': path, 'id':id, 'attr':name})
                result.append("<a href='%s'>%s</a><br/>" % (url, name))
            except (KeyError, AttributeError):
                result.append("No se pudo recuperar %s<br/>" % name)
    except (KeyError, AttributeError):
        pass
    return HttpResponse("".join(result))

