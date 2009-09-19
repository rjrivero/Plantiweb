#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

"""
Creacion y gestion de modelos y metadatos

Gestiona una cache de modelos construidos dinamicamente segun los datos
almacenados en la base de datos, y le agrega a cada modelo los metadatos
necesarios para facilitar una instropeccion lo mas independiente posible
de django. 
"""

from gettext import gettext as _
from copy import copy

from django.db import models
from plantillator.data.dataobject import Fallback

from .dbcache import Cache
from .dbcache import MetaData as MD
from .dbmodel import Dynamic


def to_unicode(self):
    """Funcion __unicode__ de los modelos generados"""
    domd = self._type._DOMD
    atts = domd.identity or domd.fields
    return u", ".join(u"%s: %s" % (x, repr(self.get(x, None))) for x in atts)


class MetaData(MD):

    """Metadatos asociados a una tabla de cliente"""


    def __init__(self, instance):

        """Procesa la instancia que define la tabla.

        instance es una instancia de Table. Esta funcion la procesa y calcula
        los metadatos asociados al modelo.

        parametros:
          -instance: instancia de la metatabla que describe al modelo

        atributos que se almacenan en el objeto:
          - filters: diccionario de filtros para los campos enlazados.

        aparte de los de dbcache.MetaData
        """
        parent = Cache[instance.parent] if instance.parent else None
        if parent:
            up = models.ForeignKey(parent, blank=True, null=True)
        else:
            @property
            def up(self):
                return Cache.data
        pk, name = instance.pk, instance.name
        fields   = set()
        dbfields = dict()
        attrs    = {
            '_up': up,
            '_id': models.AutoField(primary_key=True),

        }
        # analizo los campos normales y saco campos dinamicos.
        dynamics = self._get_fields(instance, fields, attrs, dbfields)
        # analizo los campos enlazados y saco filtros.
        filters  = self._get_links(instance, fields, attrs)
        # Creo metadata y modelo!
        super(MetaData, self).__init__(pk, name, attrs, parent)
        self.attribs, self.dbattribs = fields, dbfields
        self.identity = tuple(x.name for x in instance.uniques)
        setattr(self._type, '__unicode__', to_unicode)
        # agrego propiedades para los campos dinamicos
        self._add_dynamics(instance, dynamics)
        # agrego filtros
        self._add_filters(instance, filters)

    def _get_fields(self, instance, fields, attrs, dbfields):
        """Lee los Fields y crea una lista de campos dinamicos.
        Analiza el conjunto de campos de la instancia y
        pre-procesa los campos dinamicos:
          - Agrega el nombre y tipo de campo a "attrs"
          - Agrega el nombre de la propiedad dinamica a "fields"
          - Agrega el mapeo estatico -> dinamico a "dbfields"
          - Devuelve una lista de tuplas (Field, Dynamic)
        """
        dynamics = list()
        for field in instance.field_set.all():
            name, _name = field.name, field._name
            attrs[_name] = field.field
            fields.add(name)
            dbfields[name] = _name
            try:
                dynamic = field.dynamic
            except Dynamic.DoesNotExist:
                pass
            else:
                source_id = '<%s.%s.code>' % (instance.fullname, name)
                code = compile(dynamic.code, source_id, 'exec')
                dynamics.append((field, code))
        return dynamics

    def _build_property(self, name, hidden, code):
        """Crea una propiedad dinamica

        Crea una propiedad para que, cuando se acceda al atributo "name",
        se ejecute el codigo "code", y cuando se modifique el valor del
        atributo "name", se guarde en "hidden".
        """
        def fget(self):
            local = Fallback(Cache.data, {'self': self}, 1)
            exec code in Cache.glob, local
            return getattr(local, name)
        def fset(self, value):
            setattr(self, hidden, value)
        return property(fget, fset)

    def _add_dynamics(self, instance, dynamics):
        """Agrega una propiedad al modelo
        Agrega al modelo una propiedad por cada campo
        dinamico definido en dynamics.
        """
        for field, code in dynamics:
            name, hidden = field.name, field._name
            prop = self._build_property(name, hidden, code)
            setattr(self._type, name, prop)

    def _get_links(self, instance, fields, attrs):
        """Lee los links y crea una lista de filtros.
        Analiza el conjunto de campos de la instancia y
        pre-procesa los campos enlazados:
          - Agrega el nombre y tipo de campo a "attrs"
          - Agrega el nombre a "fields"
          - Devuelve una lista campos enlazados
        """
        groups = dict()
        for link in instance.link_set.all():
            fields.add(link._name)
            attrs[link._name] = link.field
            groups.setdefault(link.group, []).append(link)
        if not groups:
            return tuple()
        # construccion del parent_set
        # parent_set es un diccionario donde:
        # - La clave es la PK de una tabla
        # - El valor es una tuple (nombre de campo en tabla[pk], callable
        #   que obtiene el valor correspondiente a partir de un objeto
        #   de esta tabla)
        parent_set = dict()
        if instance.parent:
            for depth, ancestor in enumerate(instance.ancestors):
                parent_set[ancestor.pk] = self._pk_accessor(depth)
        filters = list()
        for group, link_set in groups.iteritems():
            # a la lista de parent_set, agrego las tablas que
            # me vengan dadas por otros campos enlazados de esta tabla
            # (siempre que sean del mismo grupo)
            table_set = copy(parent_set)
            for link in link_set:
                pk, accessor_tuple = self._link_accessor(link)
                table_set[pk] = accessor_tuple
            for link in link_set:
                filters.append((link, self._build_filter(link, table_set)))
        return filters

    def _pk_accessor(self, depth):
        """closure para obtener la PK del ancestro a la profundidad dada
        
        Encapsula una funcion que asciende en la jerarquia de ancestros
        hasta la profundidad dada (0: self.up, 1.self.up.up... etc), y
        devuelve la pk del item a esa profundidad.
        """
        def get_pk(item):
            for x in xrange(0, depth+1):
                item = item.up
            return item.pk
        return ('pk', get_pk)

    def _link_accessor(self, link):
        """closure para generar el accesor de un Link
        Dado un link, devuelve una tupla con dos elementos
            [0]: clave primaria de la tabla a la que apunta el link_set
            [1]: una segunda tupla con dos elementos:
                [0]: nombre del campo al que apunta el link en esa tabla
                [1]: un funcion que dado un item de tipo self._type,
                     devuelve el valor del link.
        """
        name, relname = link._name, link.related._name
        def accessor(item):
            return getattr(item, name)
        return (link.related.table.pk, (relname, accessor))

    def _build_filter(self, link, table_set):
        """Construye un criterio de filtrado para el campo

        "link" es el campo enlazado que queremos filtrar.
        "table_set" es un diccionario donde las claves son las PK de
            diferentes tablas. Cada elemento del diccionario es una
            tupla donde:
                - El primer elemento es el nombre de un campo de la tabla
                  identificada por la pk.
                - El segundo elemento es una funcion que, dado un objeto
                  de tipo self._type, extrae el valor que debe usarse para
                  filtrar el campo indicado de la tabla indicada.

        Lo que devuelve es una funcion que, al invocarla con un objeto
        de tipo self._type, devuelve un listado de tablas del tipo
        link.related.table que cumplen todos los criterios dados por el
        item y el table_set.

        Es un poco enrevesado, pero asi son las cosas automaticas...
        """
        table, prefix = link.related.table, '_up__'
        crits = list()
        for depth, ancestor in enumerate(table.ancestors):
            try: 
                attrib, accesor = table_set[ancestor.pk]
                field = '%s%s' % (prefix, attrib)
                crits.append((field, accesor))
            except KeyError:
                pass
            prefix = '_up__%s' % prefix
        pk = table.pk
        def filter(item):
            crit = dict((field, accesor(item)) for (field, accesor) in crits)
            model = Cache(pk)
            return model.objects.filter(**crit)
        return filter

    def _add_filters(self, instance, filters):
        self.filters = dict()
        for field, filt in filters:
            self.filters[field._name] = filt
            #source_id = '<%s.%s.filter>' % (field.table.fullname, name)
            #code = compile(field.filter, source_id, 'eval')
            #def run_filter(self):
            #    local = Fallback(Cache.data, {'self': self}, 1)
            #    for item in eval(code, Cache.glob, local):
            #        yield (getattr(item, relname), item)
            #self.filters[name] = run_filter


def model_factory(instance):
    return MetaData(instance)._type

