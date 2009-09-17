#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from itertools import chain
from datetime import datetime
from collections import namedtuple
from copy import copy
import re

from django.db import models, transaction, connection

from .dblog import app_label
from .dbcache import Cache
from .dbraw import *
from .dbfields import *


class Table(models.Model):

    """MetaTabla que define las tablas de la aplicacion"""

    objects = CatchManager()
    parent  = models.ForeignKey('self', verbose_name=_('subtabla de'),
                blank=True, null=True)
    name    = DBIdentifierField(verbose_name=_('nombre'))
    comment = models.TextField(blank=True, verbose_name=_('comentario'))

    @property
    def ancestors(self):
        "Devuelve la lista de ancestros, desde el mas cercano hasta el raiz"""
        if not self.parent:
            return tuple()
        return chain((self.parent,), self.parent.ancestors)

    @property
    def path(self):
        "Devuelve la ruta completa de tablas desde la raiz hasta esta"""
        if not self.parent:
            return (self,)
        return chain(self.parent.path, (self,))

    @property
    def fullname(self):
        """Nombre descriptivo completo"""
        return u".".join(x.name for x in self.path)

    @property
    def uniques(self):
        unique_fields = self.field_set.filter(index=UNIQUE_INDEX)
        unique_links  = self.link_set.filter(index=UNIQUE_INDEX)
        return chain(unique_fields, unique_links)

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
        pre_save_table(old_instance, old_model, self)
        super(Table, self).save()
        # invalido antes del post-save, para que la funcion
        # tenga ya disponible el nuevo modelo.
        if old_instance is not None:
            Cache.invalidate(old_instance)
        post_save_table(old_instance, old_model, self)

    @transaction.commit_on_success
    def delete(self):
        """Borra las tablas"""
        # borro antes los objetos derivados, porque una vez borrada la
        # instancia queda en un estado bastante inconsistente.
        delete_table(self, self.pk, Cache[self])
        super(Table, self).delete()


class BaseField(models.Model):

    """Modelo de campo comun para Field y Link

    En este modelo no se define la propiedad name, porque su implementacion
    es distinta en Field (campo de la base de datos) y Link (propiedad).

    Sin embargo, si que es necesario que las clases derivadas definan una
    propiedad "name" con el nombre que se usara para acceder al campo en el
    modelo.
    """

    null    = models.BooleanField(verbose_name=_('NULL'))
    index   = models.IntegerField(verbose_name=_('INDEX'), choices=(
                      (NO_INDEX,       _('sin indice')),
                      (UNIQUE_INDEX,   _('unico')),
                      (MULTIPLE_INDEX, _('multiple')),
                  ), default=NO_INDEX)
    comment = models.CharField(max_length=254, blank=True,
                               verbose_name=_('comentario'))

    # Campos que provocan cambios en las tablas generadas
    # (todos menos "comment", y se incluye "name" porque todas las
    # clases derivadas deben implementarlo)
    METAFIELDS = ['name', 'null', 'index']

    @property
    def _name(self):
        """Devuelve el nombre que tendra el campo en la base de datos"""
        return self.name

    @property
    def _idxname(self):
        """Devuelve el nombre que deben tener los indices sobre este campo.
        
        Varias clases derivadas de esta pueden definir campos de diverso tipo
        que han de incluirse en el modelo, y que pueden estar indexados.

        Los nombres de los indices de un modelo no deben coincidir entre si,
        de manera que cada clase derivada debe sobrecargar esta funcion y
        definir su propia nomenclatura para los indices.
        """
        if not self.pk:
            raise AssertionError(_("Creando indice sobre campo inexistente"))
        return "idx%d" % self.pk

    class Meta:
        abstract = True

    def __unicode__(self):
        return unicode(_("<%s> %s") % (unicode(self.table), self.name))

    def _on_changed(self, old):
        """Se invoca cuando se salva un campo modificado"""
        pass

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
            update_field(self.table, old, self)
            self._on_changed(old)
        # actualizo el modelo
        Cache.invalidate(self.table)

    @transaction.commit_on_success
    def delete(self):
        old = self.__class__.objects.get(pk=self.pk)
        old_table = old.table
        super(BaseField, self).delete()
        delete_field(old_table, old)
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
    name    = DBIdentifierField(verbose_name=_('nombre'))
    table   = models.ForeignKey(Table)
    kind    = models.CharField(max_length=32,
                  verbose_name=_('tipo'),
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
        """Construye un models.Field con los campos del objeto"""
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
        """Devuelve el valor por defecto del field"""
        return FIELDS[self.kind].default

    @property
    def _name(self):
        """Modifica el nombre si tenemos asociado codigo dinamico"""
        try:
            return self.dynamic.name
        except Dynamic.DoesNotExist:
            return self.name

    def _on_changed(self, old):
        """Actualiza los Links si se salvan cambios en el campo"""
        for link in Link.objects.filter(related=self):
            # actualizo tambien los campos que cogen su tipo de este
            update_field(link.table, link.wrap(old), link)
            Cache.invalidate(link.table)
        super(Field, self)._on_changed(old)

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

    objects  = CatchManager()
    basename = DBIdentifierField(verbose_name=_('nombre'))
    table    = models.ForeignKey(Table)
    related  = models.ForeignKey(Field, verbose_name=_('ligado a'),
                   blank=True, null=True)
    group    = models.CharField(max_length=DB_IDENTIFIER_LENGTH,
                   verbose_name=_('grupo'),
                   blank=True, null=True)
    #filter  = models.CharField(max_length=1024, verbose_name=_('filtro'))

    # Campos que provocan cambios en las tablas generadas
    METAFIELDS = list(chain(BaseField.METAFIELDS,
                            ['table', 'related']))

    @property
    def name(self):
        """Nombre compuesto por basename y grupo.
        Reemplaza al atributo "name" de BaseField
        """
        return (self.basename if not self.group
                          else u"%s_%s" % (self.basename, self.group))
    _name = name

    def wrap(self, field):
        """Devuelve un campo actualizado con los atributos del link"""
        other = copy(self)
        other.related = field
        return other

    @property
    def _idxname(self):
        """Devuelve el nombre que deben tener los indices sobre este campo"""
        if not self.pk:
            raise AssertionError(_("Creando indice sobre enlace inexistente"))
        return "lnk%d" % self.pk

    @property
    def kind(self):
        return self.related.kind

    @property
    def len(self):
        return self.related.len

    @property
    def field(self):
        return self.related.field

    @property
    def default(self):
        return self.related.default

    class Meta:
        verbose_name = _('campo de enlace')
        verbose_name_plural = _('campos de enlace')
        app_label = app_label
        unique_together = ('table', 'basename', 'group')

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

    @property
    def name(self):
        return '_%s' % str(self.related.name)

    @transaction.commit_on_success
    def save(self):
        created = not self.pk
        super(Dynamic, self).save()
        if created:
            update_dynamic(self.related, self, True)
            Cache.invalidate(self.related.table)

    @transaction.commit_on_success
    def delete(self):
        update_dynamic(self.related, self, False)
        super(Dynamic, self).delete()
        Cache.invalidate(self.related.table)


# La factoria de instancias que necesita la cache

def instance_factory(pk, parent_pk, name):
    """Localiza la instancia o instancias que cumplen los criterios dados.

    Tal como se indica en la descripcion del tipo ModelCache, esta
    factoria se comporta del modo siguiente:

      - si pk != None, ignora el resto de argumentos y devuelve
        la instancia indicada por la pk.
      - En otro caso, si name != None, devuelve una unica instancia
        cuyo parent es el indicado por parent_pk, y cuyo nombre es
        el indicado por name.
      - En el resto de casos, devuelve una lista con todas las
        instancias cuya instancia padre sea la indicada por parent_pk.

    Si no se encuentra ninguna instancia que cumpla los requisitos, se
    lanza un KeyError
    """
    try:
        if pk is not None:
            return Table.objects.get(pk=pk)
        elif name is not None:
            return Table.objects.get(parent=parent_pk, name=name)
        else:
            return Table.objects.filter(parent=parent_pk)
    except Table.DoesNotExist:
        raise KeyError(pk or name or parent_pk)
