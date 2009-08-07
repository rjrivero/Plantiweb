#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from itertools import chain
from datetime import datetime
import copy

from django.db import models, transaction, connection

from .dbraw import sql_model, sql_field
from .dbbase import BaseField, TypedField, ModelDescriptor, DBIdentifierField
from .dblog import app_label


class CatchQuerySet(models.query.QuerySet):

    def delete(self):
        # capturo la orden "delete" y la obligo a pasar uno a uno por los/erbose
        # elementos a eliminar, para que no se salte ningun evento
        for item in self:
            item.delete()


class CatchManager(models.Manager):

    def get_query_set(self):
        return CatchQuerySet(self.model)


class Table(models.Model):

    parent  = models.ForeignKey('self', verbose_name=_('subtabla de'),
                blank=True, null=True)
    name    = DBIdentifierField(verbose_name=_('nombre'))
    comment = models.TextField(blank=True, verbose_name=_('comentario'))

    def path(self):
        if not self.parent:
            return (self,)
        return chain(self.parent.path(), (self,))

    @property
    def modelname(self):
        return '_'.join(str(x.name) for x in self.path())

    @property
    def fullname(self):
        return u".".join(x.name for x in self.path())

    model   = ModelDescriptor('example', __name__)
    objects = CatchManager()
    
    def sql(self):
       return sql_model(self.model, set(self.path()))

    def __unicode__(self):
        return self.fullname

    class Meta:
        verbose_name = _('Tabla')
        verbose_name_plural = _('Tablas')
        app_label = app_label

    @transaction.commit_on_success
    def save(self, *arg, **kw):
        # tengo que hacer el cambio antes de actualizar la bd, porque
        # en otro caso, no tendria disponible el antiguo valor.
        self.model = self
        super(Table, self).save(*arg, **kw)

    @transaction.commit_on_success
    def delete(self, *arg, **kw):
        self.model = None
        super(Table, self).delete(*arg, **kw)


class Field(TypedField):

    table   = models.ForeignKey(Table)
    objects = CatchManager()

    class Meta:
        verbose_name = _('campo de datos')
        verbose_name_plural = _('campos de datos')
        app_label = app_label


class Link(BaseField):

    # solo para los campos tipo Related
    table   = models.ForeignKey(Table)
    related = models.ForeignKey(Field, verbose_name=_('ligado a'),
                blank=True, null=True)

    filter  = models.CharField(max_length=1024, verbose_name=_('filtro'))

    objects = CatchManager()

    @property
    def field(self):
        other = copy.copy(self.related)
        other.null = self.null
        return other.field

    class Meta:
        verbose_name = _('campo de enlace')
        verbose_name_plural = _('campos de enlace')
        app_label = app_label


class Dynamic(models.Model):

    # solo para los campos de tipo Dynamic
    related = models.OneToOneField(Field, verbose_name=_('ligado a'))
    code = models.TextField(verbose_name=_('codigo'))

    objects = CatchManager()

    class Meta:
        verbose_name = _('campo dinamico')
        verbose_name_plural = _('campos dinamicos')
        app_label = app_label

    def __unicode__(self):
        return unicode(_('codigo de %s') % str(self.related))

    @transaction.commit_on_success
    def save(self, *arg, **kw):
        super(Dynamic, self).save(*arg, **kw)
        # fuerzo una recarga del modelo
        table = self.related.table
        table.model = table

    @transaction.commit_on_success
    def delete(self, *arg, **kw):
        super(Dynamic, self).delete(*arg, **kw)
        # fuerzo una recarga del modelo
        table = self.related.table
        table.model = table

