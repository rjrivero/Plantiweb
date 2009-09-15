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
from django.db import models

from plantillator.data.dataobject import Fallback

from .dbcache import Cache
from .dbcache import MetaData as MD
from .dbmodel import Dynamic


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
        attrs    = {
            '_up': up,
            '_id': models.AutoField(primary_key=True),
        }
        # analizo los campos normales y saco campos dinamicos.
        dynamics = self._get_fields(instance, fields, attrs)
        # analizo los campos enlazados y saco filtros.
        filters  = self._get_links(instance, fields, attrs)
        # Creo metadata y modelo!
        super(MetaData, self).__init__(pk, name, attrs, parent)
        self.attribs = fields
        # agrego propiedades para los campos dinamicos
        self._add_dynamics(instance, dynamics)
        # agrego filtros
        self._add_filters(instance, filters)

    def _get_fields(self, instance, fields, attrs):
        """Lee los Fields y crea una lista de campos dinamicos.
        Analiza el conjunto de campos de la instancia y
        pre-procesa los campos dinamicos:
          - Agrega el nombre y tipo de campo a "attrs"
          - Agrega el nombre de la propiedad dinamica a "fields"
          - Devuelve una lista de tuplas (Field, Dynamic)
        """
        dynamics = list()
        for field in instance.field_set.all():
            fields.add(field.name)
            attrs[field._name] = field.field
            try:
                dynamics.append(field, field.dynamic)
            except Dynamic.DoesNotExist:
                pass
        return dynamics

    def _get_links(self, instance, fields, attrs):
        """Lee los links y crea una lista de filtros.
        Analiza el conjunto de campos de la instancia y
        pre-procesa los campos enlazados:
          - Agrega el nombre y tipo de campo a "attrs"
          - Agrega el nombre a "fields"
          - Devuelve una lista campos enlazados
        """
        filters = list()
        for field in instance.link_set.all():
            fields.add(field._name)
            attrs[field._name]  = field.field
            filters.append(field)
        return filters

    def _add_dynamics(self, instance, dynamics):
        """Agrega una propiedad al modelo
        Agrega al modelo una propiedad por cada campo
        dinamico definido en dynamics.
        """
        for field, dynamic in dynamics:
            source_id = '<%s.%s.code>' % (instance.fullname, field.name)
            name = field.name
            code = compile(dynamic.code, source_id, 'exec')
            prop = field._name
            def fget(self):
                local = Fallback(Cache.data, {'self': self}, 1)
                exec code in Cache.glob, local
                return getattr(local, name)
            def fset(self, value):
                setattr(self, prop, value)
            setattr(self._type, name, property(fget, fset))

    def _add_filters(self, instance, filters):
        self.filters = dict()
        for field in filters:
            name, relname = field._name, field.related.name
            source_id = '<%s.%s.filter>' % (field.table.fullname, name)
            code = compile(field.filter, source_id, 'eval')
            def run_filter(self):
                local = Fallback(Cache.data, {'self': self}, 1)
                for item in eval(code, Cache.glob, local):
                    yield (getattr(item, relname), item)
            self.filters[name] = run_filter


# Amplio la cache definiendo la factoria de modelos

def model_factory(instance):
    return MetaData(instance)._type

