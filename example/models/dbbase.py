#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain
from copy import copy

from django.db import models, backend
from django.db.models import Count

from plantillator.data.base import BaseSet, asIter
from plantillator.data.dataobject import DataType


class Deferrer(object):

    """Adapta el Deferrer de data.base para usarlo con Django"""

    def _defer(self, positive, operator, operand):
        """Devuelve una funcion f(x) == (positive, x__operator, operand)

        'positive' indica si debe usarse logica positiva (incluir los valores
        que cumplen el criterio) o negativa (excluirlos).
        """
        def decorate(colname):
            return (positive, "%s__%s" % (colname, operator), operand)
        return decorate

    def __call__(self, item):
        return self.defer(True, 'isnull', False)

    def __eq__(self, other):
        return self._defer(True, 'iexact', other)

    def __ne__(self, other):
        return self._defer(False, 'iexact', other)

    def __lt__(self, other):
        return self._defer(True, 'lt', other)

    def __le__(self, other):
        return self._defer(True, 'lte', other)

    def __gt__(self, other):
        return self._defer(True, 'gt', other)

    def __ge__(self, other):
        return self._defer(True, 'gte', other)

    def __mul__(self, other):
        """Comprueba la coincidencia con una exp. regular"""
        return self._defer(True, 'regex', other)

    def __add__(self, arg):
        """Comprueba la pertenecia a una lista"""
        return self._defer(True, 'in', asIter(arg))

    def __sub__(self, arg):
        """Comprueba la no pertenencia a una lista"""
        return self._defer(False, 'in', asIter(arg))


def _add(one, other):
    """Concatena dos sets"""
    if one._type != other._type:
        raise TypeError(other._type)
    ids = chain(asIter(one.pk), asIter(other.pk))
    objects = one._type.objects.filter(pk__in=ids)
    objects._agg = False
    objects._pos = {'pk__in': ids}
    objects._neg = dict()
    return objects


class DJSet(models.query.QuerySet):

    """QuerySet que implementa la interfaz de los DataSets"""

    def __init__(self, *arg, **kw):
        super(DJSet, self).__init__(*arg, **kw)
        # criterios que han llevado a la obtencion de este QuerySet
        self._pos = dict()
        self._neg = dict()
        # True si hay alguna columna de agregado
        self._agg = False
 
    def __call__(self, **kw):
        """Filtra el DJSet acorde al criterio especificado"""
        base = self
        if kw:
            pos, neg, agg = dict(), dict(), self._agg
            domd = self._type._DOMD
            for key, val in kw.iteritems():
                if not hasattr(val, '__call__'):
                    val = (Deferrer() == val)
                if key in domd.attribs:
                    p, crit, val = val(key)
                else:
                    child = domd.children[key]
                    agg   = True
                    refer = child._meta.object_name.lower()
                    label = '%s_count' % key
                    base  = base.annotate(**{label: Count(refer)})
                    p, crit, val = val(label)
                if p:
                    pos[crit] = val
                else:
                    neg[crit] = val
            if pos:
                base = base.filter(**pos)
            if neg:
                base = base.exclude(**neg)
            base._agg = agg
            base._pos = copy(self._pos)
            base._neg = copy(self._neg)
            base._pos.update(pos)
            base._neg.update(neg)
        return base

    def __getattr__(self, attrib):
        """Obtiene el atributo seleccionado"""
        domd = self._type._DOMD
        if attrib == 'pk' or attrib in domd.attribs:
            return BaseSet(x[attrib] for x in self.values(attrib))
        try:
            objects = domd.children[attrib].objects.all()
        except KeyError as details:
            raise AttributeError(details)
        pos, neg = dict(), dict()
        if self._agg:
            pos['_up__in'] = self.values('pk').query
        else:
            for key, val in self._pos.iteritems():
                pos['_up__%s' % key] = val
            for key, val in self._neg.iteritems():
                neg['_up__%s' % key] = val
        if pos:
            objects = objects.filter(**pos)
        if neg:
            objects = objects.exclude(**neg)
        objects._agg = False
        objects._pos = pos
        objects._neg = neg
        return objects

    def __add__(self, other):
        return _add(self, other)

    def __pos__(self):
        if len(self) == 1:
            return self[0]
        raise IndexError(0)

    @property
    def up(self):
        pos    = {'pk__in': self.values('_up').query}
        parent = self._type._DOMD.parent.objects.filter(**pos)
        parent._agg = False
        parent._pos = pos
        parent._neg = dict()
        return parent

    @property
    def _type(self):
        return self.model


class DJManager(models.Manager):

    def get_query_set(self):
        return DJSet(self.model)


class DJModel(DataType(models.Model)):

    objects = DJManager()

    class Meta(object):
        abstract = True

    def __getattr__(self, attr):
        try:
            child = self._type._DOMD.children[attr]
        except KeyError as details:
            raise AttributeError(details)
        else:
            objects = child.objects.filter(_up__exact=self.pk)
            setattr(self, attr, objects)
            return objects

    def __add__(self, other):
        return _add(self, other)

    def _choices(self, attr):
        """Devuelve una lista de posibles valores para el objeto"""
        return self._type._DOMD.filters[attr](self)

    @classmethod
    def invalidate(cls, attr):
        try:
            cls._DOMD.children.pop(attr)
        except KeyError:
            pass

