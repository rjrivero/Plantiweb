#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.http import HttpResponse
from django.shortcuts import render_to_response, get_object_or_404
from django.http import Http404

from ui.models import *


def nodelist(request, path="", id=None, attr=""):
    item  = MetaClass.data
    root  = MetaClass.root
    steps = [x for x in path.split('/') if x]
    try:
        for step in steps:
            root = root._DOMD.children[step]
    except (KeyError, AttributeError):
        raise Http404
    if not (root is MetaClass.root):
        item = get_object_or_404(root, pk=id)
    # generamos los "breadcrumbs" que nos traen hasta aqui
    crumbs = []
    brpath, britem, brattr = steps, item, attr
    while brpath:
        crumbs.append(("/"+"/".join(brpath), britem, brattr))
        brattr = brpath.pop()
        if brpath:
            britem = britem.up
    # el ultimo breadcrumb: el objeto de datos.
    crumbs.append((None, None, brattr))
    crumbs = reversed(crumbs)
    # preparamos el contexto
    data = None if not attr else getattr(item, attr)
    if data:
        # HACK
        class tmp(object):
            def __init__(self, data):
                self.data = data
                self._type = data._type
            def __iter__(self):
                for x in self.data:
                    yield x
                for x in range(0, 100):
                    yield None
        data = tmp(data)
    subpath = '/'.join((path, attr))
    return render_to_response('nodelist.html', {
        'customer': 'Demo',
        'provider': 'NextiraOne',
        'path': path,
        'subpath': subpath,
        'parent': item,
        'parent_meta': root._DOMD,
        'attr': attr,
        'data': data,
        'data_meta': data._type._DOMD,
        'crumbs': crumbs
    })

