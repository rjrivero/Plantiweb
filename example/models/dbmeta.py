#!/usr/bin/env python
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

from plantillator.data import dataobject
from plantillator.data.container import DataContainer

from .dbraw import create_model
from .dbbase import DJModel, Deferrer


class Children(dict):

    """Diccionario auto-indexado de descendientes de una tabla

    Da acceso a las instancias hijas de una cierta instancia,
    recuperandolas de la base de datos para meterlas en cache si
    aun no lo estaban.
    """

    def __init__(self, model_cache, instance):
        self.cache = model_cache
        self.pk = instance.pk

    def __getitem__(self, item):
        # intento leer el item del diccionario
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            pass
        # si falla, intento cargar el objeto de la base de datos
        try:
            objects = self.cache.metamodel.objects
            child = objects.get(parent_id=self.pk, name=item)
        except:
            raise KeyError(item)
        else:
            return self.setdefault(item, self.cache[child])

    def full(self):
        """Carga en cache todos los modelos hijos de este"""
        objects = self.cache.metamodel.objects
        for item in objects.filter(parent_id=self.pk):
            self[item.name] = self.cache[item]


class MetaData(dataobject.MetaData):

    """Metadatos asociados a una tabla de cliente"""

    def __init__(self, model_cache, instance):

        """Procesa la instancia que define la tabla.

        instance es una instancia de Table. Esta funcion la procesa y calcula
        los metadatos asociados al modelo:

        - pk: clave primaria de la instancia.
        - attribs: lista (set) de nombres de atributos.
        - summary: lista ordenada (list) de campos que describen al objeto.
        - children: diccionario de subtipos.
        - filters: diccionario de filtros para los campos enlazados.
        """
        parent = (model_cache[instance.parent] if instance.parent
                                               else model_cache.root)
        super(MetaData, self).__init__(instance.name, parent)
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
        # actualizo sumario y subtablas
        self.children = Children(model_cache, instance)
        self.summary = self.attribs[:3]
        self.pk = instance.pk

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


def RootType(model_cache):
    
    """Crea un tipo raiz (parent == None)"""

    class Root(dataobject.DataType(object)):

        """Tipo raiz (parent == None)"""

        def __init__(self):
            super(Root, self).__init__()
            self._cache = set()

        def __getattr__(self, attr):
            """Busca una tabla con el nombre dado y parent NULL"""
            try:
                objects  = model_cache.metamodel.objects
                instance = objects.get(parent=None, name=attr)
                objects  = model_cache[instance].objects.all()
            except model_cache.metamodel.DoesNotExist:
                raise AttributeError(attr)
            else:
                self._cache.add(attr)
                setattr(self, attr, objects)
                return objects

        def invalidate(self, item=None):
            """Invalida la cache de objetos, o el item indicado"""
            if item is None:
                for item in self._cache:
                    delattr(self, item)
                self._cache = set()
            elif item in self._cache:
               delattr(self, item)
               self._cache.delete(item)

    rootmeta = dataobject.MetaData('ROOT', None)
    rootmeta.post_new(Root)
    return Root


def model_unicode(self):
    """Devuelve una representacion unicode del objeto"""
    return u", ".join((u"%s:%s" % (field, repr(self[field])))
                      for field in self._type._DOMD.summary)


class ModelCache(DataContainer):

    """Cache de modelos"""

    def __init__(self, metamodel, app_label, module):
        """Inicia el constructor de tipos."""
        self.models = dict()
        self.metamodel = metamodel
        self.app_label = app_label
        self.module = module
        DataContainer.__init__(self, RootType(self), Deferrer, None)

    def __getitem__(self, obj):
        """Recupera o crea un modelo"""
        if not obj.pk:
            # Solo permitimos crear objetos ya salvados, para evitar problemas
            # de cache y para tener el nombre de la tabla a mano.
            raise ValueError('pk is None')
        try:
            return self.models[obj.pk]
        except KeyError:
            return self.models.setdefault(obj.pk, self.create_model(obj))

    def invalidate(self, instance=None):
        """Elimina todos los modelos anteriores a la revision actual"""
        if instance is None:
            self.models = dict()
            self.data.invalidate()
        else:
            self.remove_model(instance)
            top = instance.path[0]
            self.data.invalidate(top.name)

    def create_model(self, obj):
        """Crea el modelo asociado a una instancia"""
        attrs = {
            '_id': models.AutoField(primary_key=True),
            '__unicode__': model_unicode,
        }
        attrs.update(dict((f._db_name(), f.field)
                     for f in obj.field_set.all()))
        attrs.update(dict((f.name, f.field)
                     for f in obj.link_set.all()))
        if obj.parent:
            parent_model = self[obj.parent]
            # la clave primaria debe permitir valores NULL para poder
            # cambiar el parent de una tabla dinamicamente.
            attrs['_up'] = models.ForeignKey(parent_model,
                               blank=True, null=True)
        else:
            # si un objeto no tiene padre, arreglo la clase derivada para
            # que "up" devuelva el objeto de datos raiz.
            attrs['_up']  = property(lambda x: self.data)
        name, bases = obj.modelname, (DJModel,)
        meta  = MetaData(self, obj)
        model = create_model(name, self.app_label, self.module, attrs, bases)
        meta.post_new(model, self.glob, self.data)
        return model

    def remove_model(self, instance):
        """Desvincula un modelo que va a ser modificado"""
        if not instance.pk:
            return
        for obj in self.metamodel.objects.filter(parent=instance.pk):
            self.remove_model(obj)
        try:
            del(self.models[instance.pk])
        except KeyError:
            pass

