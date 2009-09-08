#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


try:
    import cPickle as pickle
except ImportError:
    import pickle
import re

from django.db import models


class DBIdentifierField(models.CharField):

    """Tipo de columna que representa un nombre de tabla o campo valido

    Solo se aceptan los campos que cumplan con la regexp
    DBIdentifierField._VALID
    """

    _VALID = re.compile('^[a-zA-Z][\w\d_]{0,15}$')

    def __init__(self, *arg, **kw):
        """Construye el campo y limita su longitud"""
        kw['max_length'] = 16
        super(DBIdentifierField, self).__init__(*arg, **kw)

    def to_python(self, value):
        """Se asegura de que el valor es valido, o lanza ValueError"""
        value = super(DBIdentifierField, self).to_python(value)
        if value is not None and not DBIdentifierField._VALID.match(value):
            raise ValueError(value)
        return value
 
    def get_db_prep_save(self, value):
        """Se asegura de que el valor es valido, o lanza ValueError"""
        if value is not None and not DBIdentifierField._VALID.match(value):
            raise ValueError(value)
        return super(DBIdentifierField, self).get_db_prep_save(value)


class BoundedIntegerField(models.PositiveIntegerField):

    """Tipo de columna que representa un entero acotado"""

    _VALID = re.compile('^[a-zA-Z][\w\d_]{0,15}$')

    def __init__(self, lower, upper, *arg, **kw):
        """Define limites inferior y superior de la cota"""
        self.lower = lower
        self.upper = upper
        super(BoundedIntegerField, self).__init__(*arg, **kw)

    def to_python(self, value):
        """Se asegura de que el valor es valido, o lanza ValueError"""
        value = super(BoundedIntegerField, self).to_python(value)
        if value is not None and (value < self.lower or value > self.upper):
            raise ValueError(value)
        return value
 
    def get_db_prep_save(self, value):
        """Se asegura de que el valor es valido, o lanza ValueError"""
        if value is not None and (value < self.lower or value > self.upper):
            raise ValueError(value)
        return super(BoundedIntegerField, self).get_db_prep_save(value)


class PickledObject(str):

    """A subclass of string so it can be told whether a string is
       a pickled object or not (if the object is an instance of this class
       then it must [well, should] be a pickled one)."""

    pass


class PickledObjectField(models.Field):

    """Objecto serializable para almacenar en base de datos"""

    __metaclass__ = models.SubfieldBase

    def to_python(self, value):
        if isinstance(value, PickledObject):
            return pickle.loads(str(value))
        else:
            try:
                return pickle.loads(str(value))
            except:
                return value

    def get_db_prep_save(self, value):
        if value is not None and not isinstance(value, PickledObject):
            value = PickledObject(pickle.dumps(value))
        return value

    def get_internal_type(self): 
        return 'TextField'

    def get_db_prep_lookup(self, lookup_type, value):
        if lookup_type == 'exact':
            value = self.get_db_prep_save(value)
            return super(PickledObjectField, self).get_db_prep_lookup(
                       lookup_type, value)
        elif lookup_type == 'in':
            value = [self.get_db_prep_save(v) for v in value]
            return super(PickledObjectField, self).get_db_prep_lookup(
                       lookup_type, value)
        else:
            raise TypeError('Lookup type %s is not supported.' % lookup_type)


TOKEN_SPLIT = u','
TOKEN_SEP = u':'


class LabeledIdentifier(unicode):

    """Identificador etiquetado.

    Cadena unicode que contiene un identificador valido (un valor valido
    para un campo DBIdentifierField), y que ademas tiene un atributo "label"
    que puede servir para etiquetar 
    """

    def __new__(cls, string):
        try:
            label, content = string.split(TOKEN_SEP, 1)
        except ValueError:
            label, content = None, string
        else:
            label = label.strip()
        obj = unicode.__new__(cls, content.strip())
        obj.label = label or None
        if not DBIdentifierField._VALID.match(obj):
            raise ValueError(string)
        return obj

    def labeled(self):
        return self if not self.label else TOKEN_SEP.join((self.label, self))


class TokenTuple(tuple):

    """Tupla de identificadores separados por coma

    Cada identificador puede tener una etiqueta, que es una cadena de texto
    que precede al identificador, separada por ':'.

    Por ejemplo,
    "nombre: name, descripcion: description"

    El constructor puede recibir una cadena con el formato descrito arriba,
    o una tupla de LabeledIdentifiers 
    """

    def __new__(cls, value):
        if not hasattr(value, '__iter__'):
            value = (x.strip() for x in value.split(TOKEN_SPLIT))
            value = (LabeledIdentifier(x) for x in value if x)
        return tuple.__new__(cls, value)

    def __unicode__(self):
        return self.labeled()

    def __str__(self):
        return str(unicode(self))

    def labeled(self):
        return TOKEN_SPLIT.join(x.labeled() for x in self)


class SeparatedValuesField(models.CharField):

    """Campo que contiene una lista de identificadores separados por ','"""

    def to_python(self, value):
        return TokenTuple(value)

    def get_db_prep_value(self, value):
        return TokenTuple(value).labeled()
 

class CatchQuerySet(models.query.QuerySet):

    """QuerySet que intercepta la orden delete

    Intercepta la orden delete para obligar a que los elementos del QuerySet
    sean borrados uno a uno, en lugar de en batch. De esta forma, se invoca
    al metodo "delete" de cada uno.
    """

    def delete(self):
        # capturo la orden "delete" y la obligo a pasar uno a uno por los
        # elementos a eliminar, para que no se salte ningun evento
        for item in self:
            item.delete()


class CatchManager(models.Manager):

    """Manager que devuelve QuerySets del tipo CatchQuerySet"""

    def get_query_set(self):
        return CatchQuerySet(self.model)

