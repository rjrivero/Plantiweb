#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain
from collections import namedtuple

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required

from .base import with_profile
from .homecontext import HomeContext


class GridRow(tuple):

    """Fila del grid que representa esta vista.

    Una fila del grid tiene las siguientes celdas:
      - Una celda por cada tipo "parent", con su identidad.
      - Una celda por cada campo summary o hidden accesible para el usuario

    Las celdas tienen dos atributos:
      - css: clase CSS de la celda
      - value: valor de la celda.
    """

    GridCell = namedtuple("GridItem", "css, value")

    @staticmethod
    def make_item(instance, attrib, domd):
        if attrib in domd.dynamics:
            val = getattr(instance, domd.dbattribs[attrib], None)
            if val is not None:
                return GridRow.GridCell("item_dynamic", unicode(val))
        val = getattr(instance, attrib)
        val = unicode(val) if val is not None else u""
        return GridRow.GridCell("", val)

    def __new__(cls, pathitem, attribs, domd):
        parents, instance = pathitem
        parents = (GridRow.GridCell("", unicode(x)) for x in parents)
        values  = (GridRow.make_item(instance, x, domd) for x in attribs)
        obj = super(GridRow, cls).__new__(cls, chain(parents, values))
        obj.pk = instance.pk
        return obj


@login_required
@with_profile
def gridview(request, pk=None):
    hc = HomeContext(request)
    items = hc.run_query(request, hc['q'], int(pk) if pk is not None else None)
    # "customizo" los datos para hacer su representacion mas facil.
    if items:
        parents = hc['item_parents']
        summary = hc['item_summary']
        hiddens = hc['item_hiddens']
        # este parametro lo usa el template para calcular a partir de
        # que numero de columna empiezan los campos "hidden"
        hc['item_fixedcount'] = len(parents) + len(summary)
        attribs = tuple(chain(summary, hiddens))
        domd = hc['model']._DOMD
        items = tuple(GridRow(x, attribs, domd) for x in items)
        hc['item_griddata'] = items
    return render_to_response('datanav/grid.html', hc,
        context_instance=RequestContext(request))
