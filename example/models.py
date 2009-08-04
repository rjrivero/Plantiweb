#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
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


class ModelDescriptor(object):

    def __init__(self, app_label, module):
        """Inicia el constructor de tipos"""
        self.models = dict()
        self.app_label = app_label
        self.module = module

    def model_create(self, instance):
        """Crea el modelo asociado a una instancia"""
        attrs = dict((f.name, f.field) for f in instance.field_set.all())
        if instance.parent:
            parent_model = self.get_model(instance.parent)
            attrs['_up'] = models.ForeignKey(parent_model)
        return model_create(instance.name, self.app_label, self.module, attrs)

    def __get__(self, instance, owner):
        """Obtiene el modelo asociado a una instancia"""
        if not instance:
            raise AttributeError(_("modelo"))
        try:
            model = self.models[instance.pk]
        except KeyError:
            model = self.model_create(instance)
            self.models[instance.pk] = model
        return model


class FieldDescriptor(object):

    @staticmethod
    def choices():
        return ( 
            ('CharField',      _('texto')),
            ('IntegerField',   _('numero')),
            ('IPAddressField', _('IP')),
            ('Related',        _('enlace'))
        )

    def _CharField(self, instance):
        return models.CharField(max_length=instance.len,
                                blank=instance.null, null=instance.null)

    def _IntegerField(self, instance):
        return models.IntegerField()

    def _IPAddressField(self, instance):
        return models.IPAddressField()

    def _Related(self, instance):
        other = copy.copy(instance.related)
        other.null = instance.null
        return other.field

    def __get__(self, instance, owner):
        if not instance:
            raise AttributeError('field')
        func = getattr(self, '_%s' % instance.kind)
        return func(instance)


class Table(models.Model):

    parent  = models.ForeignKey('self', verbose_name=_('subtabla de'),
                blank=True, null=True)
    name    = models.CharField(max_length=16, verbose_name=_('nombre'))
    comment = models.TextField(blank=True, verbose_name=_('comentario'))

    # No lo hago porque eso lo dejo para clases derivadas
    # que puedan establecer el app_name y el module
    # model = ModelDescriptor('app_name', 'module')

    def known(self):
        if not self.parent:
            return set()
        known = self.parent.known()
        known.add(self.parent.model)
        return known

    def sql(self):
       return model_sql(self.model, self.known())

    def __unicode__(self):
        if self.parent:
            return u".".join(unicode(self.parent), self.name)
        return self.name

    model = ModelDescriptor('example', __name__)


class Field(models.Model):

    # no se puede tener una relacion con una clas abstracta
    table   = models.ForeignKey(Table, verbose_name=_('tabla'))
    name    = models.CharField(max_length=16, verbose_name=_('nombre'))
    kind    = models.CharField(max_length=32, verbose_name=_('tipo'),
                choices=FieldDescriptor.choices())
    null    = models.BooleanField(verbose_name=_('NULL'))
    comment = models.TextField(blank=True, verbose_name=_('comentario'))
    # solo para los campos de tipo Dynamic
    code    = models.TextField(verbose_name=_('codigo'), blank=True, null=True)
    # solo para los campos tipo CharField
    len     = models.IntegerField(verbose_name=_('longitud'))
    # solo para los campos tipo Related
    related = models.ForeignKey('self', verbose_name=_('ligado a'),
                blank=True, null=True)

    def sql(self):
        meta  = self.table.model._meta
        model = model_create('test', meta.app_label, meta.__module__,
                    {self.name: self.field})
        return model_sql(model)[0].split("\n")[1].strip()[:-1]

    def __unicode__(self):
        return unicode(_("<%s> %s") % (unicode(self.table), self.name))

    field = FieldDescriptor()

