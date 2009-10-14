#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


import numbers
from itertools import chain
from copy import copy

from django.db import models, backend
from django.db.models import Count, Q

from plantillator.data.base import BaseSet, asIter
from plantillator.data.dataobject import DataType


class QueryItem(object):

    """Encapsula una consulta, similar a un objeto Q de django"""

    def __init__(self, pos, field, value, agg):
        """Crea el objeto con los criterios de la consulta.

        - pos: True si usar logica positiva (como filter), false en otro
               caso (como exclude).
        - field: combinacion de nombre de campo y operador (ef: 'pk__exact')
        - value: valor a usar en la comparacion.
        - agg: True si el campo es un valor calculado (average, count...)
        """
        self.pos = pos
        self.field = field
        self.value = value
        self.agg = agg

    def q(self):
        """Devuelve el objeto Q correspondiente a esta consulta"""
        query = Q(**{self.field: self.value})
        return query if self.pos else ~query

    def __and__(self, other):
        """Combina esta consulta con otra (AND)"""
        return AndQuery(self, other)

    def __or__(self, other):
        """Combina esta consulta con otra (OR)"""
        return OrQuery(self, other)

    def __invert__(self):
        """Invierte la logica de la consulta"""
        return QueryItem(not self.pos, self.field, self.value, self.agg)

    def up(self):
        """Genera una copia agregando el sufijo "_up" a todos los campos"""
        if self.agg:
            raise AttributeError('up')
        return QueryItem(self.pos, "_up__%s" % str(self.field), self.value, False)

    def __unicode__(self):
        return u"Query: (%s) %s == %s [agg: %s]" % (
                   str(self.pos), self.field,
                   repr(self.value), str(self.agg)) 


def ChainQuery(op, combinator):

    """Query encadenada

    Reune varias queries del mismo tipo (AND u OR).
    """

    op = unicode(op)

    class _ChainQuery(QueryItem):

        def __init__(self, *queries):
            self.queries = queries and list(queries) or list()

        def up(self):
            cls = self.__class__
            return cls(*tuple(q.up() for q in self.queries))

        def __iter__(self):
            return self.queries.__iter__()

        def q(self):
            if not self.queries:
                return Q()
            return reduce(combinator, (query.q() for query in self))

        def __unicode__(self):
            return op.join(unicode(q) for q in self)

        def extend(self, query):
            """Agrega los componentes de una query
            (las dos queries deben ser del mismo tipo)
            """
            assert isinstance(query, self.__class__)
            self.queries.extend(query.queries)

        def append(self, query):
            """Agrega una query como un todo"""
            self.queries.append(query)

    return _ChainQuery


class AndQuery(ChainQuery(" AND ", lambda a, b: a & b)):

    def __invert__(self):
        return OrQuery(*tuple(~q for q in self))


class OrQuery(ChainQuery(" OR ", lambda a, b: a | b)):

    def __invert__(self):
        return AndQuery(*tuple(~q for q in self))


class Deferrer(object):

    """Adapta el Deferrer de data.base para usarlo con Django"""

    def _defer(self, pos, operator, value):
        """Devuelve un QueryItem

        'pos' indica si debe usarse logica positiva (incluir los valores
        que cumplen el criterio) o negativa (excluirlos).
        'agg' indica si la columna sobre la que se esta filtrando es un
        agregado o no.
        """
        def decorate(colname, agg):
            return QueryItem(pos, "%s__%s" % (colname, operator), value, agg)
        return decorate

    def __call__(self, colname, agg):
        return QueryItem(True, "%s__isnull" % colname, False, agg)

    def __eq__(self, other):
        operator = isinstance(other, numbers.Real) and 'exact' or 'iexact'
        return self._defer(True, operator, other)

    def __ne__(self, other):
        operator = isinstance(other, numbers.Real) and 'exact' or 'iexact'
        return self._defer(False, None, other)

    def __gt__(self, other):
        operator = isinstance(other, numbers.Real) and 'gt' or 'istartswith'
        return self._defer(True, operator, other)

    def __ge__(self, other):
        operator = isinstance(other, numbers.Real) and 'gte' or 'istartswith'
        return self._defer(True, operator, other)

    def __lt__(self, other):
        operator = isinstance(other, numbers.Real) and 'lt' or 'iendswith'
        return self._defer(True, operator, other)

    def __le__(self, other):
        operator = isinstance(other, numbers.Real) and 'lte' or 'iendswith'
        return self._defer(True, operator, other)

    def __mul__(self, other):
        """Comprueba la coincidencia con una exp. regular"""
        #return self._defer(True, 'regex', other)
        return self._defer(True, 'icontains', other)

    def __add__(self, arg):
        """Comprueba la pertenecia a una lista"""
        if isinstance(arg, DJValueSet):
            # para hacer una subquery, y no sacara los
            # datos antes de hacer la consulta.
            arg = arg._queryset.values(arg._attrib)
        else:
            arg = asIter(arg)
        return self._defer(True, 'in', arg)

    def __sub__(self, arg):
        """Comprueba la no pertenencia a una lista"""
        if isinstance(arg, DJValueSet):
            # para hacer una subquery, y no sacara los
            # datos antes de hacer la consulta.
            arg = arg._queryset.values(arg._attrib)
        else:
            arg = asIter(arg)
        return self._defer(False, 'in', arg)


class DJQuerySet(models.query.QuerySet):

    """QuerySet que implementa la interfaz de los DataSets"""

    def __init__(self, *arg, **kw):
        super(DJQuerySet, self).__init__(*arg, **kw)
        # criterios que han llevado a la obtencion de este QuerySet
        self._crit = None
 
    def _build_crit(self, kw):
        """Construye un QueryItem con los criterios especificados"""
        base, crit, domd = self, AndQuery(), self._type._DOMD
        for key, val in kw.iteritems():
            if not hasattr(val, '__call__'):
                val = (Deferrer() == val)
            if key in domd.attribs:
                additional = val(key, False)
            else:
                child = domd.children[key]
                refer = child._meta.object_name.lower()
                label = '%s_count' % key
                base  = base.annotate(**{label: Count(refer)})
                additional = val(label, True)
            crit.append(additional)
        return (base, crit)

    def __call__(self, **kw):
        """Filtra el resultado usando criterios adicionales"""
        base, crit = self._build_crit(kw)
        base = base.filter(crit.q())
        base._crit = crit
        if self._crit:
            base._crit.extend(self._crit)
        return base

    def __getattr__(self, attrib):
        """Obtiene el atributo seleccionado"""
        domd = self._type._DOMD
        if attrib == 'pk' or attrib in domd.attribs:
            if attrib in domd.dynamics:
                # el campo es calculado, no tengo mas remedio
                # que calcularlo por cada elemento del set.
                return BaseSet(getattr(x, attrib) for x in self)
            else:
                # el campo no es calculado, puedo demorar la consulta
                return DJValueSet(self, attrib)
        try:
            objects = domd.children[attrib]._DOMD.objects
        except KeyError as details:
            raise AttributeError(details)
        if not self._crit:
            return objects.all()
        try:
            # si puedo, intento cambiar el nombre de los campos
            # del criterio para que la cosa se resuelva con un join
            crit = self._crit.up()
        except AttributeError:
            # si hay cambos agregados, es mejor usar una subquery.
            crit = QueryItem(True, '_up__in', self.values('pk'), False)
            crit = AndQuery(crit)
        objects = objects.filter(crit.q()).all()
        objects._crit = crit
        return objects

    def __add__(self, other):
        return _add(self, other)

    def __pos__(self):
        if len(self) == 1:
            return self[0]
        raise IndexError(0)

    @property
    def up(self):
        # esto siempre lo resuelvo con subqueries
        crit = QueryItem(True, 'pk__in', self.values('_up_id'), False)
        parents = self._type._DOMD.parent._DOMD.objects.filter(crit.q()).all()
        parents._crit = AndQuery(crit)
        return parents

    @property
    def _type(self):
        return self.model


class DJValueSet(object):

    """Encapsula un ValuesQuerySet.

    Proporciona los metodos habituales de filtrado, acceso, etc
    """

    def __init__(self, queryset, attrib):
        """Construye un DJValueSet a partir de un DJQuerySet y un atributo"""
        self._queryset = queryset
        self._attrib = attrib
        self._valueset = queryset.values(attrib)

    def __call__(self, arg):
        return DJValueSet(self._queryset(**{self._attrib: arg}), self._attrib)

    def __add__(self, other):
        if (isinstance(other, DJValueSet) and 
            self._queryset._type == other._queryset._type and
            self._attrib == other._attrib):
            return DJValueSet(self._queryset + other._queryset, self._attrib)
        return BaseSet(chain(self, other))

    def __iter__(self):
        for item in self._valueset(self._attrib):
            yield item[self._attrib]


class DJManager(models.Manager):

    def get_query_set(self):
        return DJQuerySet(self.model)


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
            objects = child._DOMD.objects.filter(_up__exact=self.pk).all()
            setattr(self, attr, objects)
            return objects

    def __add__(self, other):
        return _add(self, other)

    def _choices(self, attr):
        """Devuelve una lista de posibles valores para el objeto"""
        return self._type._DOMD.filters[attr](self)

    @property
    def _crit(self):
        """Devuelve un QueryItem que identifica este objeto"""
        return QueryItem(True, 'pk__exact', self.pk, False)

    @classmethod
    def invalidate(cls, attr):
        try:
            cls._DOMD.children.pop(attr)
        except KeyError:
            pass


def _add(one, other):
    """Concatena dos sets"""
    if one._type != other._type:
        raise TypeError(other._type)
    objects = one._type._DOMD.objects
    c1, c2 = one._crit, other._crit
    if not c1 or not c2:
        # Cuando no hay filtro es como pk=cualquiera, no esta filtrado.
        # asi que el resultado de un OR cuando uno de los elementos
        # no esta filtrado, es la tabla entera sin filtrar.
        return objects.all()
    crit = OrQuery(c1, c2)
    objects = objects.filter(crit.q()).all()
    objects._crit = AndQuery(crit)
    return objects

