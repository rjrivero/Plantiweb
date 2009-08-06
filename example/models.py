#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from itertools import chain
import copy
from django.db import models
from django.core.management import sql, color
from django.db import connection


def model_create(name, app_label, module, attrs=None):
    class Meta:
        pass
    setattr(Meta, 'app_label', app_label)
    attrs = attrs or dict()
    attrs.update({'Meta': Meta, '__module__': module})
    return type(str(name), (models.Model,), attrs)


def model_sql(model, known=None):
    style = color.no_style()
    return connection.creation.sql_create_model(model, style, known)[0]

def field_sql(model, field):
    model = model_create('test', model._meta.app_label, model.__module__,
                {self.name: self.field})
    return model_sql(model)[0].split("\n")[1].strip()[:-1]


class ModelDescriptor(object):

    def __init__(self, app_label, module):
        """Inicia el constructor de tipos"""
        self.models = dict()
        self.app_label = app_label
        self.module = module

    def model_create(self, obj):
        """Crea el modelo asociado a una instancia"""
        attrs = dict((f.name, f.field) for f in obj.field_set.all())
        attrs.update(dict((f.name, f.field) for f in obj.dynamic_set.all()))
        attrs.update(dict((f.name, f.field) for f in obj.link_set.all()))
        if obj.parent:
            parent_model = self.model_get(obj.parent)
            attrs['_up'] = models.ForeignKey(parent_model)
        return model_create(obj.modelname, self.app_label, self.module, attrs)

    def model_get(self, obj):
        try:
            model = self.models[obj.pk]
        except KeyError:
            model = self.model_create(obj)
            self.models[obj.pk] = model
        return model

    def __get__(self, instance, owner):
        """Obtiene el modelo asociado a una instancia"""
        if not instance:
            raise AttributeError(_("modelo"))
       	return self.model_get(instance)


class Table(models.Model):

    parent  = models.ForeignKey('self', verbose_name=_('subtabla de'),
                blank=True, null=True)
    name    = models.CharField(max_length=16, verbose_name=_('nombre'))
    comment = models.TextField(blank=True, verbose_name=_('comentario'))

    # No lo hago porque eso lo dejo para clases derivadas
    # que puedan establecer el app_name y el module
    # model = ModelDescriptor('app_name', 'module')

    def path(self):
        if not self.parent:
            return (self,)
        return chain(self.parent.path(), (self,))

    @property
    def modelname(self):
        return '_'.join(str(x.name).capitalize() for x in self.path())

    @property
    def fullname(self):
        return u".".join(x.name for x in self.path())

    def sql(self):
       return model_sql(self.model, set(self.path()))

    model = ModelDescriptor('example', __name__)

    def __unicode__(self):
        return self.fullname

    class Meta:
        verbose_name = _('Tabla')
        verbose_name_plural = _('Tablas')


class BaseField(models.Model):

    table   = models.ForeignKey(Table, verbose_name=_('tabla'))
    name    = models.CharField(max_length=16, verbose_name=_('nombre'))
    null    = models.BooleanField(verbose_name=_('NULL'))
    comment = models.CharField(max_length=254, blank=True,
                               verbose_name=_('comentario'))

    def sql(self):
        return field_sql(self.table.model, self.field)

    class Meta:
        abstract = True

    def __unicode__(self):
        return unicode(_("<%s> %s") % (unicode(self.table), self.name))


class TypedField(BaseField):

    def CharField(self):
        return models.CharField(max_length=self.len,
                                blank=self.null, null=self.null)

    def IntegerField(self):
        return models.IntegerField(blank=self.null, null=self.null)

    def IPAddressField(self):
        return models.IPAddressField(blank=self.null, null=self.null)
    
    @property
    def field(self):
        return getattr(self, str(self.kind))()

    # no se puede tener una relacion con una clas abstracta
    kind    = models.CharField(max_length=32, verbose_name=_('tipo'),
                  choices=(
                      ('CharField',      _('texto')),
                      ('IntegerField',   _('numero')),
                      ('IPAddressField', _('IP')),
                ))

    # solo para los campos tipo CharField
    len     = models.IntegerField(verbose_name=_('longitud'),
                                  blank=True, null=True)

    class Meta:
        abstract = True


class Field(TypedField):

    class Meta:
        verbose_name = _('Campo de datos')
        verbose_name_plural = _('Campos de datos')


class Dynamic(TypedField):

    # solo para los campos de tipo Dynamic
    code = models.TextField(verbose_name=_('codigo'))

    class Meta:
        verbose_name = _('Campo dinamico')
        verbose_name_plural = _('Campos dinamicos')


class Link(BaseField):

    # solo para los campos tipo Related
    related = models.ForeignKey(Field, verbose_name=_('ligado a'),
                blank=True, null=True)

    filter  = models.TextField(verbose_name=_('filtro'))

    @property
    def field(self):
        other = copy.copy(self.related)
        other.null = instance.null
        return other.field

    class Meta:
        verbose_name = _('Campo de enlace')
        verbose_name_plural = _('Campos de enlace')

