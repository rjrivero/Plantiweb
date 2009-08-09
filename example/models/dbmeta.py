#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from itertools import chain
from datetime import datetime
from collections import namedtuple
from copy import copy
import re

from django.db import models, transaction, connection

from .dbraw import *
from .dbbase import ModelDescriptor
from .dblog import app_label


class DBIdentifierField(models.CharField):

    """Tipo de columna que representa un nombre de tabla o campo valido

    Solo se aceptan los campos que cumplan con la regexp DBIdentifierField._VALID
    """

    _VALID = re.compile('^[a-zA-Z][\w\d_]{0,15}$')

    def __init__(self, *arg, **kw):
        """Construye el campo y limita su longitud"""
        kw['max_length'] = 16
        super(DBIdentifierField, self).__init__(*arg, **kw)

    def to_python(self, value):
        """Se asegura de que el valor es valido, en otro caso lanza ValueError"""
        value = super(DBIdentifierField, self).to_python(value)
        if value is not None and not DBIdentifierField._VALID.match(value):
            raise ValueError(value)
        return value
 
    def get_db_prep_save(self, value):
        """Se asegura de que el valor es valido, en otro caso lanza ValueError"""
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
        """Se asegura de que el valor es valido, en otro caso lanza ValueError"""
        value = super(BoundedIntegerField, self).to_python(value)
        if value is not None and (value < self.lower or value > self.upper):
            raise ValueError(value)
        return value
 
    def get_db_prep_save(self, value):
        """Se asegura de que el valor es valido, en otro caso lanza ValueError"""
        if value is not None and (value < self.lower or value > self.upper):
            raise ValueError(value)
        return super(BoundedIntegerField, self).get_db_prep_save(value)


class CatchQuerySet(models.query.QuerySet):

    """QuerySet que intercepta la orden delete

    Intercepta la orden delete para obligar a que los elementos del QuerySet
    sean borrados uno a uno, en lugar de en batch. De esta forma, se invoca el
    metodo "delete" de cada uno.
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


class Table(models.Model):

    """MetaTabla que define las tablas de la aplicacion"""

    objects = CatchManager()
    parent  = models.ForeignKey('self', verbose_name=_('subtabla de'),
                blank=True, null=True)
    name    = DBIdentifierField(verbose_name=_('nombre'))
    comment = models.TextField(blank=True, verbose_name=_('comentario'))

    def path(self):
        """Lista de ancestros de la tabla, incluyendose a si misma"""
        if not self.parent:
            return (self,)
        return chain(self.parent.path(), (self,))

    @property
    def modelname(self):
        """Nombre para el modelo"""
        return '_'.join(str(x.name) for x in self.path())

    @property
    def fullname(self):
        """Nombre descriptivo completo"""
        return u".".join(x.name for x in self.path())

    # Un DataDescriptor que da acceso al modelo
    model = ModelDescriptor('example', __name__)

    class Meta:
        verbose_name = _('Tabla')
        verbose_name_plural = _('Tablas')
        app_label = app_label

    @transaction.commit_on_success
    def save(self, *arg, **kw):
        # Obtengo el valor antiguo, antes de salvar y de limpiar cache
        old_instance = old_model = None
        if self.pk:
            old_instance = Table.objects.get(pk=self.pk)
            old_model = old_instance.model
        # Salvo los datos antes de crear la tabla, para forzar la validacion
        super(Table, self).save(*arg, **kw)
        # borro la cache de modelos
        self.model = None
        update_table(old_instance, old_model, self)

    @transaction.commit_on_success
    def delete(self, *arg, **kw):
        # me guardo una copia del modelo para poder borrar los datos
        model = self.model
        # borro tabla y datos
        super(Table, self).delete(*arg, **kw)
        delete_table(self.model)
        # limpio cache de modelos
        self.model = None

    def __unicode__(self):
        return self.fullname


NO_INDEX       = 0
UNIQUE_INDEX   = 1
MULTIPLE_INDEX = 2

class BaseField(models.Model):

    """Modelo de campo comun para Field y Link"""

    name    = DBIdentifierField(verbose_name=_('nombre'))
    null    = models.BooleanField(verbose_name=_('NULL'))
    index   = models.IntegerField(verbose_name=_('INDEX'), choices=(
                      (NO_INDEX,       _('sin indice')),
                      (UNIQUE_INDEX,   _('unico')),
                      (MULTIPLE_INDEX, _('multiple')),
                  ), default=NO_INDEX)
    comment = models.CharField(max_length=254, blank=True,
                               verbose_name=_('comentario'))

    # Campos que provocan cambios en las tablas generadas
    # (todos menos "comment")
    METAFIELDS = ['name', 'null', 'index']

    class Meta:
        abstract = True

    def _get_links(self):
        """Devuelvo una lista de todos los "Links" relacionados con este campo"""
        return tuple()

    @transaction.commit_on_success
    def save(self, *arg, **kw):
        if not self.pk:
            changed, old = True, None
        else:
            changed, old = False, self.__class__.objects.get(pk=self.pk)
            for x in self.__class__.METAFIELDS:
                if getattr(old, x) != getattr(self, x):
                    changed = True
                    break
        # Salvo los cambios antes de modificar, para forzar la validacion.
        model = self.table.model # cacheo el modelo pre-cambios
        super(BaseField, self).save(*arg, **kw)
        if changed:
            update_field(self.table, old, self)
            for link in self._get_links():
                # actualizo tambien los campos que cogen su tipo de este
                update_field(link.table, link.wrap(old), link)
                link.table.model = None
        # actualizo el modelo
        self.table.model = None

    @transaction.commit_on_success
    def delete(self, *arg, **kw):
        old = self.__class__.objects.get(pk=self.pk)
        super(BaseField, self).delete(*arg, **kw)
        delete_field(self.table, old) 
        # fuerzo una recarga del modelo
        self.table.model = self.table

    def __unicode__(self):
        return unicode(_("<%s> %s") % (unicode(self.table), self.name))


X = namedtuple('X', 'verbose, default, field, params')
FIELDS = {
    'CharField':      X('texto',  '', models.CharField,      {'max_length': 'len'}),
    'IPAddressField': X('IP',     '', models.IPAddressField, {}),
    'IntegerField':   X('numero', 0,  models.IntegerField,   {}),
}


class Field(BaseField):

    """Campo tipado de la base de datos"""
    
    objects = CatchManager()
    table   = models.ForeignKey(Table)
    kind    = models.CharField(max_length=32, verbose_name=_('tipo'), choices=list(
                  (name, _(x.verbose)) for name, x in FIELDS.iteritems()))
    # solo para los campos tipo CharField
    len     = BoundedIntegerField(1, 1024, verbose_name=_('longitud'),
                  blank=True, null=True)

    # Campos que provocan cambios en las tablas generadas
    # posiblemente todos menos "comment"
    METAFIELDS = list(chain(BaseField.METAFIELDS, ['table', 'kind',  'len']))

    @property
    def field(self):
        attrs = FIELDS[self.kind]
        ftype = attrs.field
        fparm = dict((x, getattr(self, y)) for x, y in attrs.params.iteritems())
        fparm['blank'] = fparm['null'] = self.null
        fparm['db_index'] = (self.index == MULTIPLE_INDEX)
        fparm['unique'] = (self.index == UNIQUE_INDEX)
        return ftype(**fparm)

    @property
    def default(self):
        return FIELDS[self.kind].default

    class Meta:
        verbose_name = _('campo de datos')
        verbose_name_plural = _('campos de datos')
        app_label = app_label

    def _get_links(self):
        """Devuelvo una lista de todos los "Links" relacionados con este campo"""
        return Link.objects.filter(related=self.pk)


class Link(BaseField):

    """Campo anclado a un campo tipado, hereda sus caracteristicas"""

    objects = CatchManager()
    table   = models.ForeignKey(Table)
    related = models.ForeignKey(Field, verbose_name=_('ligado a'),
                blank=True, null=True)
    filter  = models.CharField(max_length=1024, verbose_name=_('filtro'))

    # Campos que provocan cambios en las tablas generadas
    METAFIELDS = list(chain(BaseField.METAFIELDS, ['table', 'related']))

    def wrap(self, field):
        """Devuelve un campo actualizado con los atributos definidos en el link"""
        other = copy(field)
        other.table = self.table
        other.name = self.name
        other.null = self.null
        other.index = self.index
        return other

    @property
    def field(self):
        return self.wrap(self.related).field

    @property
    def default(self):
        return FIELDS[self.related.kind].default

    class Meta:
        verbose_name = _('campo de enlace')
        verbose_name_plural = _('campos de enlace')
        app_label = app_label


class Dynamic(models.Model):

    """Modificador de campo que lo convierte en dinamico"""

    objects = CatchManager()
    related = models.OneToOneField(Field, verbose_name=_('ligado a'))
    code = models.TextField(verbose_name=_('codigo'))

    class Meta:
        verbose_name = _('campo dinamico')
        verbose_name_plural = _('campos dinamicos')
        app_label = app_label

    @transaction.commit_on_success
    def save(self, *arg, **kw):
        super(Dynamic, self).save(*arg, **kw)
        # fuerzo una recarga del modelo
        self.related.table.model = None

    @transaction.commit_on_success
    def delete(self, *arg, **kw):
        super(Dynamic, self).delete(*arg, **kw)
        # fuerzo una recarga del modelo
        self.related.table.model = None

    def __unicode__(self):
        return unicode(_('codigo de %s') % str(self.related))

