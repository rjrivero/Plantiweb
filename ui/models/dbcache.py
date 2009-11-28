#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from itertools import chain
from copy import copy

# HACKISH - HACKISH - HACKISH
from django.db.models.loading import cache

from plantillator.data.base import normalize
from plantillator.data.container import DataContainer
from plantillator.data.dataobject import DataType
from plantillator.data.dataobject import MetaData as MD

from .dbbase import DJModel, Deferrer


VARIABLES_TABLE = 'variables'
VARIABLES_KEY = 'nombre'
VARIABLES_VALUE = 'valor'

APP_LABEL  = 'auto'
APP_MODULE = __name__


class ModelChildren(dict):

    """Diccionario auto-indexado de descendientes de una tabla

    Da acceso a las instancias hijas de una cierta instancia,
    recuperandolas de la base de datos para meterlas en cache si
    aun no lo estaban.
    """

    def __init__(self, pk):
        dict.__init__(self)
        self.pk = pk
        self.full = False

    def __getitem__(self, item):
        # intento leer el item del diccionario
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            pass
        # si falla, intento cargar el objeto de la base de datos
        return self.setdefault(item, Cache(None, self.pk, item))

    def all(self):
        """Carga en cache todos los modelos hijos de este"""
        if not self.full:
            for model in Cache(None, self.pk):
                self[model._DOMD.name] = model
            self.full = True
        return self

    def invalidate(self, attr=None):
        """Invalida un atributo"""
        if not attr:
            self.clear()
        else:
            try: del(self[attr])
            except KeyError: pass
        self.full = False


class RootType(DataType(object)):

    """Tipo raiz (parent == None)"""

    def __init__(self, *arg, **kw):
        super(RootType, self).__init__(*arg, **kw)
        self._vartab = None
        self._varattr = set()

    def __getattr__(self, attr):
        """Busca una atributo indicado en el espacio raiz

        Primero, busca tablas con el nombre indicado y parent == None.
        Si no encuentra nada, busca en las entradas de la tabla especial
        VARIABLES_TABLE.
        """
        try:
            # lo busco como subtabla
            child_domd = self._type._DOMD.children[attr]._DOMD
            objects = child_domd.objects.all()
            # Si hago el setattr, los datos no se actualizan tras salvar
            # setattr(self, attr, objects)
            return objects
        except KeyError:
            # lo busco como variable
            self._vartab = self._vartab or Cache(None, None, VARIABLES_TABLE)
            if self._vartab:
                try:
                    objs = self._vartab.objects.all()
                    item = (+objs(**{VARIABLES_KEY: attr}))
                except IndexError:
                    pass
                else:
                    result = normalize(getattr(item, VARIABLES_VALUE))
                    self._varattr.add(attr)
                    setattr(self, attr, result)
                    return result
        raise AttributeError(attr)

    def invalidate(self, attr=None):
        """Invalida la cache de objetos, o el item indicado"""
        children = self._type._DOMD.children
        if attr:
            attrs = (attr,)
            self._varattr.discard(attr)
        else:
            attrs = chain(self._varattr, children.keys())
            self._varattr = set()
        for attr in attrs:
            try: delattr(self, attr)
            except: pass
        children.invalidate(attr)


class RootMeta(MD):

    """Metadatos asociados al tipo raiz"""

    def __init__(self):
        """Metadatos basicos asociados a un modelo."""
        super(RootMeta, self).__init__(copy(RootType), 'RootType', None)
        self.pk = None
        self.children = ModelChildren(None)


class MetaData(MD):

    """Metadatos asociados a una tabla de cliente"""

    def __init__(self, pk, name, attrs, parent=None):
        """Metadatos basicos asociados a un modelo.

        Los datos que recibe son:
            pk:     La clave primaria que identifica al modelo.
            name:   El nombre "amigable" del modelo. Este nombre se
                    usa como indice en la tabla "ModelChildren" del
                    modelo padre, y como atributo en las instancias del
                    modelo para acceder a las subtablas.
            attrs:  Los atributos de la clase a crear.
            parent: El modelo padre de este.
        """
        # creo el modelo y el objeto
        # El nombre del modelo puede repetirse en la jerarquia de tablas,
        # sin embargo para django debe ser unico. Por eso, le pongo como
        # sufijo la clave primaria antes de crear el tipo.
        mid = "%s_%d" % (name, pk)
        cls = MetaData.create_model(mid, attrs, Cache.app_label, Cache.module)
        super(MetaData, self).__init__(cls, name, parent or Cache.root)
        # inicializo variables
        self.pk = pk
        self.children = ModelChildren(pk)
        # localizo el ancestro de mas alto nivel
        top = self
        while top.parent._DOMD.pk:
            top = top.parent._DOMD
        self.top = top._type

    @staticmethod
    def create_model(name, attrs, app_label=APP_LABEL, module=APP_MODULE, base=DJModel):
        """Crea el modelo asociado a una instancia"""
        class Meta:
            pass
        setattr(Meta, 'app_label', app_label)
        setattr(Meta, 'db_table', '%s_%s' % (app_label, name))
        attrs.update({'Meta': Meta, '__module__': module})
        # HACKISH - HACKISH - HACKISH
        #
        # Django guarda una cache de modelos, y cuando se intenta crear
        # uno que ya esta en cache, en vez de actualizar la cache con el
        # modelo nuevo, devuelve el modelo antiguo.
        #
        # Esto es muy malo para nuestros propositos, asi que a continuacion
        # pongo un hack que elimina el modelo de la cache, si existia
        app_cache = cache.app_models.get(app_label, dict())
        try:
            del(app_cache[name.lower()])
        except KeyError:
            pass
        # Ahora ya puedo crear el modelo
        return type(str(name), (base,), attrs)


class ModelCache(DataContainer):

    """Cache de modelos - objeto singleton

    Para completar la cache y permitir que funcione, es necesario
    asignarle al objeto dos atributos:

    - model_factory: callable que, dada una instancia, devuelva un modelo.
    - instance_factory: callable que devuelva la instancia o instancias que
                        cumplan ciertas condiciones.

    instance_factory se invoca con tres argumentos:
    - pk: clave primaria de la instancia que se busca.
    - parent_pk: pk de la instancia padre de la que se busca.
    - name: nombre de la instancia que se busca.

    La funcion debe hacer lo siguiente:
      - si pk != None, debe ignorar el resto de argumentos y devolver
        la instancia indicada por la pk.
      - En otro caso, si name != None, debe devolver una unica instancia
        cuyo parent sea el indicado por parent_pk, y cuyo nombre sea
        el indicado por name.
      - En el resto de casos, debe devolver una lista con todas las
        instancias cuya instancia padre sea la indicada por parent_pk.

    Si no se encuentra ninguna instancia que cumpla los requisitos, debe
    lanzarse un KeyError.
    """

    Singleton = None

    def __new__(cls, root_type, deferrer_type, filter_type):
        if not ModelCache.Singleton:
            self = object.__new__(cls)
            self.started = False
            self.instance_factory = None
            self.model_factory = None
            self.app_label = APP_LABEL
            self.module = APP_MODULE
            ModelCache.Singleton = self
        return ModelCache.Singleton

    def __init__(self, root_type, deferrer_type, filter_type):
        if not self.started:
            self.started = True
            super(ModelCache, self).__init__(root_type, deferrer_type, filter_type)
            self.models = dict()

    def __getitem__(self, instance, loop=set()):
        """Recupera o crea un modelo.
        "instance" debe ser un objeto con al menos dos atributos:
          - "pk": clave primaria del modelo a recuperar.
          - "model": atributo o descriptor que genere el modelo.
        """
        pk = instance.pk
        if not pk:
            # Solo permitimos crear objetos ya salvados, para evitar problemas
            # de cache y para tener el nombre de la tabla a mano.
            raise ValueError(_('pk es Nulo'))
        try:
            return self.models[pk]
        except KeyError:
            pass
        # para evitar referencias circulares, implementamos un mecanismo
        # antibucles
        if pk in loop:
            raise ValueError, _("Referencia circular (%s)") % repr(pk)
        loop.add(pk)
        try:
            return self.models.setdefault(pk, self.model_factory(instance))
        finally:
            loop.remove(pk)

    def __call__(self, instance_pk=None, parent_pk=None, instance_name=None):
        """Localiza el modelo asociado a una cierta instancia.

        Localiza un modelo en funcion de ciertos parametros:
        - pk: Clave primaria de la instancia que define al modelo.
        - parent_pk: clave primaria de la instancia padre del modelo
        - instance_name: nombre de la instancia

        Si solo se especifica instance_pk: devuelve un unico modelo.
        Si solo se especifica parent_pk: devuelve una lista de modelos hijo.
        Si se especifica parent_pk y name: devuelve el modelo de la tabla
           hija de "parent_pk" cuyo nombre coincida con "instance_name"
        """
        item = self.instance_factory(instance_pk, parent_pk, instance_name)
        if instance_pk or instance_name:
            # el resultado debe ser una unica instancia
            return self[item]
        return (self[x] for x in item)

    def get(self, pk, defval=None):
        return self.models.get(pk, defval)

    def invalidate(self, instance=None):
        """Elimina el modelo de la instancia indicada y sus ancestros.
        "instance" debe ser un objeto con al menos dos atributos:
          - "pk": clave primaria del modelo a recuperar.
          - "model": atributo o descriptor que genere el modelo.
        """
        if instance is None:
            self.models.clear()
            self.data.invalidate()
        else:
            model = self.pop(instance.pk)
            if model:
                domd = model._DOMD
                parent, top = domd.parent, domd.top
                # elimino la entrada de "children" en el ancestro
                # (solo si el ancestro no es el root; en otro caso, basta
                # con el self.data.invalidate que se hace abajo)
                if parent != top:
                    parent._DOMD.children.invalidate(domd.name)
                self.data.invalidate(top._DOMD.name)
 
    def pop(self, pk):
        """Elimina un modelo y sus descendientes"""
        try:
            model = self.models.pop(pk)
        except KeyError:
            return
        else:
            for child in model._DOMD.children.values():
                self.pop(child._DOMD.pk)
            return model


Cache = ModelCache(RootMeta()._type, Deferrer, None)

