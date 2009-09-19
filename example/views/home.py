#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required

from .base import with_profile
from ..models import Field, Link, Table


DEFAULT_HIST_LEN = 10


class Filter(object):

    """Representa un criterio de filtrado sobre una tabla"""

    MODEL_NOT_FOUND = _("El modelo con pk = '%s' no existe")
    MODEL_NOT_ALLOWED = _("No esta autorizado a acceder al modelo '%s'")
    FTYPE_NOT_FOUND = _("El id de campo '%s' no es valido")
    EMPTY_FTYPE = _("El id de campo no puede estar vacio")
    FIELD_NOT_FOUND = _("No existe el campo con id '%s'")
    FIELD_NOT_ALLOWED = _("No esta autorizado a ver el campo '%s'")
    NO_OPERATORS = _("No existen operadores para el tipo de campo '%s'")
    OP_NOT_FOUND = _("No existe el operador '%s'")

    STRING_OPERATORS = {
        'cualquiera': (None, _('cualquiera'), None),
        'exact': ('__iexact', _('igual'), str),
        'startswith': ('__istartswith', _('empieza por'), str),
        'endswith': ('__iendswith', _('termina en'), str),
    }

    INT_OPERATORS = {
        'cualquiera': (None, _('cualquiera'), None),
        'exact': ('__exact', _('igual'), int),
        'gt': ('__gt', _('mayor'), int),
        'lt': ('__lt', _('menor'), int),
    }

    OPERATORS = {
        'CharField': STRING_OPERATORS,
        'IPAddressField': STRING_OPERATORS,
        'IntegerField': INT_OPERATORS,
    }

    def resolve_field(self, model, ff):
        """Obtiene el campo del modelo identificado por ff.

        ff es un identificador de campo de una tabla. Puede referirse
        a un campo normal (Field), a un campo tipado (Link), o a una
        subtabla (un Child).

        Esta funcion reconoce el formato de ff, busca el campo al
        que se refiere, y localiza el objeto.

        Devuelve una tupla (identificador de tipo, objeto)
        """
        if len(ff) < 2:
            raise ValueError(Filter.EMPTY_FTYPE)
        flag, pk = ff[0], int(ff[1:])
        if flag == 'F':
            fmodel, fobjects = Field, Field.objects
        elif flag == 'L':
            fmodel, fobjects = Link, Link.objects
        elif flag == 'C':
            fmodel = Table
            fobjects = Table.objects.filter(parent=model._DOMD.pk)
        else:
            raise ValueError(Filter.FTYPE_NOT_FOUND % ff)
        try:
            field = fobjects.get(pk=pk)
        except fmodel.DoesNotExist:
            raise ValueError(Filter.FIELD_NOT_FOUND % ff)
        return (flag, field)

    def pack_field(self, flag, pk):
        """Inversa de resolve_field"""
        return "%s%d" % (flag, pk)

    def __init__(self, request, ft, ff, fo, fv):
        """Comprueba la validez de un filtro
        Los parametros que recibe son:
        - ft: primary key de una tabla.
        - fl: primary key de un Field, Link o Child:
              - Si es field, empieza por 'F'
              - Si es link, empieza por 'L'
              - Si es una subtabla, empieza por 'C'
        - fo: operador a aplicar
        - fv: valor con el que comparar el campo.

        Comprueba que:
        - ft es una tabla valida y el usuario tiene permiso para verla.
        - fl es un campo valido y el usuario tiene permiso para verlo.
        - fo es un operador valido para el tipo de campo.
        - fv es un valor valido para el tipo de campo.
        """
        try:
            model = Cache(int(ft))
        except KeyError:
            raise ValueError(Filter.MODEL_NOT_FOUND % str(ft))
        profile = request.session['profile']
        fields = profile.fields(model)
        if not fields:
            raise ValueError(Filter.MODEL_NOT_ALLOWED % model.fullname)
        flag, field = self.resolve_field(model, str(ff))
        if not field.name in fields:
            raise ValueError(Filter.FIELD_NOT_ALLOWED % field.name)
        operators = Filter.OPERATORS.get(field.kind, None)
        if not operators:
            raise ValueError(Filter.NO_OPERATORS % field.kind)
        opdata = operators.get(fo, None)
        if not opdata:
            raise ValueError(Filter.OP_NOT_FOUND % str(fo))
        op, label, optype = opdata
        self.pk = model._DOMD.pk
        self.flag = ff_flag
        self.fpk = field.pk
        self.op = op
        self.label = label
        self.value = optype(fv)


class HomeView(dict):

    """Prepara la vista raiz"""

    def __init__(self, request):
        super(dict, self).__init__()
        self.add_history(request)
        self.add_filters(request)

    def add_history(self, request):
        """Actualiza el historico de comandos"""
        history = request.session.setdefault('history', [])
        q = request.GET.get('q', u'')
        h = int(request.GET.get('h', DEFAULT_HIST_LEN))
        h_list = (5, 10, 15, 20, 25)
        changed = False
        if 0 < h <= h_list[-1]:
            if len(history) > h:
                history = history[:h]
                changed = True
        else:
            h = h_list[-1]
        if q:
            try:
                selected = history.index(q)
            except ValueError:
                selected = 0
                history.insert(0, q)
                changed = True
        if changed:
            request.session['history'] = history
        self.update(**locals())
        return q

    def add_filters(self, request):
        """Actualiza la lista de filtros"""
        filters = request.session.setdefault('filters', [])
        ft = request.GET('ft', None)
        ff = request.GET('ff', None)
        fo = request.GET('fo', None)
        fv = request.GET('fv', None)
        changed = False
        if ft and ff and fo:
            try:
                new_filter = Filter(request, ft, ff, fo, fv)
            except ValueError:
                pass
            else:
                filters.append(new_filter)
                changed = True
        #applied_filters = self.apply_filters(filters)
        if changed:
            request.session['filters'] = filters
        self.update(**locals())
        return filters


@login_required
@with_profile
def homeview(request):
    return render_to_response('datanav/home.html',
        HomeView(request),
        context_instance=RequestContext(request))

