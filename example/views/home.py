#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required

from .base import with_profile
from ..models import Field, Link


DEFAULT_HIST_LEN = 10


class HomeView(dict):

    """Prepara la vista raiz"""

    STRING_OPERATORS = {
        'cualquiera': (None, _('cualquiera'), None),
        '__iexact': ('__iexact', _('igual'), str),
        '__istartswith': ('__istartswith', _('empieza por'), str),
        '__iendswith': ('__iendswith', _('termina en'), str),
    }

    INT_OPERATORS = {
        'cualquiera': (None, _('cualquiera'), None),
        '__exact': ('__exact', _('igual'), int),
        '__gt': ('__gt', _('mayor'), int),
        '__lt': ('__lt', _('menor'), int),
    }

    OPERATORS = {
        'CharField': STRING_OPERATORS,
        'IPAddressField': STRING_OPERATORS,
        'IntegerField': INT_OPERATORS,
    }
 
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
            new_filter = self.build_filter(ft, ff, fo, fv)
            if new_filter:
                filters.append(new_filter)
                changed = True
        potential_filters = self.potential_filters(filters)
        if changed:
            request.session['filters'] = filters
        self.update(**locals())
        return filters

    def build_filter(self, ft, ff, fo, fv):
        """Comprueba la validez de un filtro
        Los parametros que recibe son:
        - ft: primary key de una tabla.
        - fl: primary key de un Field o Link:
              - Si es field, empieza por 'F'
              - Si es link, empieza por 'L'
        - fo: operador a aplicar
        - fv: valor con el que comparar el campo.

        Comprueba que:
        - ft es una tabla valida y el usuario tiene permiso para verla.
        - fl es un campo valido y el usuario tiene permiso para verlo.
        - fo es un operador valido para el tipo de campo.
        - fv es un valor valido para el tipo de campo.
        """
        model = Cache(int(ft))
        if not model:
            print "El modelo con pk = %s no existe" % str(ft)
            return
        profile = request.session['profile']
        fields = profile.fields(model)
        if not fields:
            print "El usuario no esta autorizado a acceder al modelo %s" % model.fullname
            return
        ff = str(ff)
        if ff.startswith('F'):
            fmodel = Field
            ff_flag = 'F'
        elif ff.startswith('L'):
            fmodel = Link
            ff_flag = 'L'
        else:
            print "El id de campo especificado no es valido"
            return 
        try:
            field = fmodel.objects.get(pk=int(ff[1:]))
        except fmodel.DoesNotExist:
            print "No existe el campo con id %s en la tabla %s" % (ff, model.fullname)
            return 
        if not field.name in fields:
            print "El usuario no esta autorizado a ver el campo %s (%s)" % (field.name, str(fields))
            return
        try:
            operators = HomeView.OPERATORS[field.kind]
        except KeyError:
            print "No existen operadores para el tipo de campo (%s)" % (field.kind)
            return
        try:
            op, label, optype = operators[fo]
        except KeyError:
            print "No existe el operador %s" % str(fo)
            return
        return (model._DOMD.pk, ff_flag, field.pk, op, optype(fv))

    def trusted_filter(self, ft, ff_flag, ff, op, fv):
        """Construye un filtro con los parametros ya validados
        Los parametros que recibe son:
        - ft: primary key de una tabla.
        - ff_flag:
              - 'F' si se quiere filtrar sobre un Field
              - 'L' si se filtra sobre un Link
        - fl: primary key del Field / Link
        - op: operador a aplicar
        - label: etiqueta del operador, para listas
        - fv: valor con el que filtrar
        """
        model = Cache(int(ft))
        fmodel = Field if ff_flag = 'F' else Link
        field = fmodel.objects.get(pk=ff)
        return (model, field, op, fv)

    def potential_filters(filters):
        trusted_filters = (self.trusted_filter(x) for x in filters)
        potential = dict()
        for model, field, op, fv in trusted_filters:
            potential[model._DOMD.pk] = model
            for submodel in model._DOMD.children.all():
                potential[submodel._DOMD.pk] = submodel
        for pk, model in potential:
            pass
        self.update(**locals())
        
        

@login_required
@with_profile
def homeview(request):
    return render_to_response('datanav/home.html',
        HomeView(request),
        context_instance=RequestContext(request))

