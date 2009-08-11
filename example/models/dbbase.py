#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
import re
import copy

from django.db import models, transaction
from plantillator.data import dataobject
from plantillator.djread.djdata import DJModel

from .dbraw import create_model
from .dblog import ChangeLog


class Children(dict):

    """Diccionario auto-indexado de descendientes de una tabla

    Da acceso a las instancias hijas de una cierta instancia, recuperandolas
    de la base de datos para meterlas en cache si aun no lo estaban.
    """

    def __init__(self, instance):
        self.instance = instance

    def __getitem__(self, item):
        # intento leer el item del diccionario
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            pass
        # si falla, intento cargar el objeto de la base de datos
        try:
            child = self.instance.table_set.get(name=item)
        except:
            raise KeyError(item)
        else:
            return self.setdefault(item, child.model)

    def full(self):
        for item in self.instance.table_set.all():
            self[item.name] = item.model


class MetaData(dataobject.MetaData):

    """Metadatos asociados a una tabla de cliente"""

    def __init__(self, instance, root):
        """Procesa la instancia que define la tabla.

        instance es una instancia de Table. Esta funcion la procesa y devuelve
        los metadatos asociados al modelo.
        """
        super(MetaData, self).__init__(instance.name, instance.parent or root)
        # analizo los campos dinamicos
        self.attribs, self.dynamic = [], dict()
        for field in instance.field_set.all():
            self.attribs.append(field.name)
            try:
                code = field.dynamic.code
            except:
                pass
            else:
                source_id = '<%s.%s.code>' % (instance.fullname, field.name)
                self.dynamic[field.name] = compile(code, source_id, 'exec')
        # analizo los filtros
        self.filters = dict()
        for field in instance.link_set.all():
            self.attribs.append(field.name)
            self.filters[field.name] = field
        self.summary = self.attribs[:3]
        self.children = Children(instance)

    def post_new(self, cls, glob, data):
        """Agrega a la clase las propiedades y filtros adecuados"""
        super(MetaData, self).post_new(cls)
        # construyo propiedades para los campos dinamicos
        for attrib, code in self.dynamic.iteritems():
            static = '_%s' % str(attrib)
            def fget(self):
                local = dataobject.Fallback(data, {'self': self}, 1)
                exec code in glob, local
                return getattr(local, attrib)
            def fset(self, value):
                setattr(self, static, value)
            setattr(cls, attrib, property(fget, fset))
        # preparo los filtros:
        for attrib, field in self.filters.iteritems():
            relname = field.related.name
            source_id = '<%s.%s.filter>' % (field.table.fullname, field.name)
            code = compile(field.filter, source_id, 'eval')
            def run_filter(self):
                for item in eval(code, glob, data):
                    yield (getattr(item, relname), item)
            self.filters[attrib] = run_filter

    def choices(self, item, attr):
        """Devuelve una lista de alternativas para el campo, si es enlazado"""
        try:
            return list(self.filters[attr](item))
        except KeyError:
            return None


class ModelCache(object):

    def __init__(self, app_label, module, root):
        """Inicia el constructor de tipos"""
        self.models = dict()
        self.app_label = app_label
        self.module = module
        self.root = root
        self.data = root()
        self.glob = dict()

    def get_model(self, obj):
        """Recupera o crea un modelo"""
        if not obj.pk:
            # Solo permitimos crear objetos ya salvados, para evitar problemas
            # de cache y para tener el nombre de la tabla a mano.
            raise ValueError('pk is None')
        try:
            return self.models[obj.pk]
        except KeyError:
            return self.models.setdefault(obj.pk, self.create_model(obj))

    def create_model(self, obj):
        """Crea el modelo asociado a una instancia"""
        attrs = {'_id': models.AutoField(primary_key=True)}
        attrs.update(dict((f._db_name(), f.field) for f in obj.field_set.all()))
        attrs.update(dict((f.name, f.field) for f in obj.link_set.all()))
        if obj.parent:
            parent_model = obj.parent.model
            attrs['_up'] = models.ForeignKey(parent_model)
        else:
            # si un objeto no tiene padre, arreglo la clase derivada para
            # que "up" devuelva el objeto de datos raiz.
            attrs['_up']  = property(lambda x: self.data)
        name, bases = obj.modelname, (DJModel,)
        model = create_model(name, self.app_label, self.module, attrs, bases)
        meta  = MetaData(obj, self.root)
        # marco el objeto con la revision del changelog
        meta.rev = ChangeLog.objects.current().pk
        meta.post_new(model, self.glob, self.data)
        return model

    def remove_model(self, instance):
        """Desvincula un modelo que va a ser modificado"""
        if not instance.pk:
            return
        for obj in instance.__class__.objects.filter(parent=instance.pk):
            self.remove_model(obj)
        try:
            del(self.models[instance.pk])
        except KeyError:
            pass

    def invalidate(self):
        """Elimina todos los modelos anteriores a la revision actual"""
        current = ChangeLog.objects.current().pk
        invalid = set()
        for pk, model in self.models.iteritems():
            if model._DOMD.rev < current:
                invalid.add(pk)
        for pk in invalid:
            del(self.models[pk])

