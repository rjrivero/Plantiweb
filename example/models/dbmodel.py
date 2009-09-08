#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from itertools import chain
from datetime import datetime
from collections import namedtuple
from copy import copy
import re

from django.db import models, transaction, connection

from .dblog import app_label
from .dbmeta import ModelCache
from .dbraw import update_table, delete_table
from .dbraw import update_field, delete_field, update_dynamic
from .dbfields import *


class Table(models.Model):

    """MetaTabla que define las tablas de la aplicacion"""

    objects = CatchManager()
    parent  = models.ForeignKey('self', verbose_name=_('subtabla de'),
                blank=True, null=True)
    name    = DBIdentifierField(verbose_name=_('nombre'))
    comment = models.TextField(blank=True, verbose_name=_('comentario'))

    def __init__(self, *arg, **kw):
        super(Table, self).__init__(*arg, **kw)

    @property
    def path(self):
        if not self.parent:
            return (self,)
        return tuple(chain(self.parent.path, (self,)))

    @property
    def modelname(self):
        """Nombre para el modelo"""
        if not self.pk:
            raise ValueError, _('El modelo aun no ha sido salvado')
        return "%s_%d" % (str(self.name), self.pk)

    @property
    def fullname(self):
        """Nombre descriptivo completo"""
        return u".".join(x.name for x in self.path)

    class Meta:
        verbose_name = _('Tabla')
        verbose_name_plural = _('Tablas')
        app_label = app_label
        unique_together = ('parent', 'name')

    def __unicode__(self):
        return self.fullname

    @transaction.commit_on_success
    def save(self):
        """Crea o modifica la tabla en la base de datos"""
        old_instance, old_model = None, None
        if self.pk:
            old_instance = Table.objects.get(pk=self.pk)
            old_model = Cache[old_instance]
        super(Table, self).save()
        if old_instance is not None:
            Cache.invalidate(old_instance)
        update_table(Cache, old_instance, old_model, self)

    @transaction.commit_on_success
    def delete(self):
        """Borra las tablas"""
        # borro antes los objetos derivados, porque una vez borrada la
        # instancia queda en un estado bastante inconsistente.
        delete_table(Cache, self, self.pk, Cache[self])
        super(Table, self).delete()


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

    def _db_name(self):
        """Devuelve el nombre que tendra el campo en el modelo"""
        return self.name

    def _get_links(self):
        """Devuelvo una lista de los "Links" relacionados con el campo"""
        return tuple()

    class Meta:
        abstract = True

    def __unicode__(self):
        return unicode(_("<%s> %s") % (unicode(self.table), self.name))

    @transaction.commit_on_success
    def save(self):
        """Modifica los campos de las tablas en la bd"""
        sender, old, changed = self.__class__, None, True
        if self.pk:
            old = sender.objects.get(pk=self.pk)
            changed = any((getattr(old, x) != getattr(self, x))
                          for x in sender.METAFIELDS)
        super(BaseField, self).save()
        if changed:
            update_field(Cache, self.table, old, self)
            for link in self._get_links():
                # actualizo tambien los campos que cogen su tipo de este
                update_field(Cache, link.table, link.wrap(old), link)
                Cache.invalidate(link.table)
        # actualizo el modelo
        Cache.invalidate(self.table)

    @transaction.commit_on_success
    def delete(self):
        old = self.__class__.objects.get(pk=self.pk)
        old_table = old.table
        super(Basefield, self).delete()
        delete_field(Cache, old_table, old)
        Cache.invalidate(old_table)


X = namedtuple('X', 'verbose, default, field, params')
FIELDS = {
    'CharField':      X('texto',  '', models.CharField, {'max_length': 'len'}),
    'IPAddressField': X('IP',     '', models.IPAddressField, {}),
    'IntegerField':   X('numero', 0,  models.IntegerField,   {}),
}


class Field(BaseField):

    """Campo tipado de la base de datos"""
    
    objects = CatchManager()
    table   = models.ForeignKey(Table)
    kind    = models.CharField(max_length=32, verbose_name=_('tipo'),
                  choices=list(
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
        fparm = dict((x, getattr(self, y))
                     for x, y in attrs.params.iteritems())
        fparm['blank'] = fparm['null'] = self.null
        # No utilizo los mecanismos de django para crear indices, sino que
        # uso directamente la base de datos. Esto es porque django no ofrece
        # facilidades para borrar los indices una vez creados.
        #fparm['db_index'] = (self.index == MULTIPLE_INDEX)
        #fparm['unique'] = (self.index == UNIQUE_INDEX)
        return ftype(**fparm)

    @property
    def default(self):
        return FIELDS[self.kind].default

    def _dynamic_name(self, dynamic=False):
        """Devuelve el nombre normal, o el dinamico"""
        return str(self.name) if not dynamic else ('_%s' % str(self.name))

    def _db_name(self):
        """Modifica el nombre si tenemos asociado codigo dinamico"""
        try:
            dynamic = self.dynamic
        except Dynamic.DoesNotExist:
            dynamic = None
        return self._dynamic_name(dynamic)

    def _get_links(self):
        """Devuelvo una lista de todos los "Links" del campo"""
        return Link.objects.filter(related=self.pk)

    def save(self):
        """Compruebo que estan definidos los campos adicionales del tipo"""
        field = FIELDS[self.kind]
        for param, attr in field.params.iteritems():
            if not getattr(self, attr):
                raise ValueError(_("'%s' no puede estar vacio!" % attr))
        super(Field, self).save()

    class Meta:
        verbose_name = _('campo de datos')
        verbose_name_plural = _('campos de datos')
        app_label = app_label
        unique_together = ('table', 'name')


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
        """Devuelve un campo actualizado con los atributos del link"""
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
        unique_together = ('table', 'name')

    def __unicode__(self):
        return unicode(_("enlace %s a %s") % (self.name, str(self.related)))


class Dynamic(models.Model):

    """Modificador de campo que lo convierte en dinamico"""

    objects = CatchManager()
    related = models.OneToOneField(Field, verbose_name=_('ligado a'))
    code = models.TextField(verbose_name=_('codigo'))

    class Meta:
        verbose_name = _('campo dinamico')
        verbose_name_plural = _('campos dinamicos')
        app_label = app_label

    def __unicode__(self):
        return unicode(_('codigo de %s') % str(self.related))

    @transaction.commit_on_success
    def save(self):
        created = not self.pk
        super(Dynamic, self).save()
        if created:
            update_dynamic(Cache, self.related, True)
            Cache.invalidate(self.related.table)

    @transaction.commit_on_success
    def delete(self):
        related = self.related
        super(Dynamic, self).delete()
        update_dynamic(Cache, related, False)
        Cache.invalidate(related.table)


Cache = ModelCache(Table, app_label, __name__)

