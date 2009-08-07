#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
import re
import copy

from django.db import models, transaction

from .dbraw import *


class DBIdentifierField(models.CharField):

    _VALID = re.compile('^[a-zA-Z][\w\d_]{0,15}$')

    def __init__(self, *arg, **kw):
        kw['max_length'] = 16
        super(DBIdentifierField, self).__init__(*arg, **kw)

    def to_python(self, value):
        value = super(DBIdentifierField, self).to_python(value)
        if value and not DBIdentifierField._VALID.match(value):
            raise ValueError(value)
        return value
 
    def get_db_prep_save(self, value):
        if value and not DBIdentifierField._VALID.match(value):
            raise ValueError(value)
        return super(DBIdentifierField, self).get_db_prep_save(value)


class BoundedIntegerField(models.PositiveIntegerField):

    _VALID = re.compile('^[a-zA-Z][\w\d_]{0,15}$')

    def __init__(self, lower, upper, *arg, **kw):
        self.lower = lower
        self.upper = upper
        super(BoundedIntegerField, self).__init__(*arg, **kw)

    def to_python(self, value):
        value = super(BoundedIntegerField, self).to_python(value)
        if value is None or value < self.lower or value > self.upper:
            raise ValueError(value)
        return value
 
    def get_db_prep_save(self, value):
        if value is None or value < self.lower or value > self.upper:
            raise ValueError(value)
        return super(BoundedIntegerField, self).get_db_prep_save(value)


class ModelDescriptor(object):

    def __init__(self, app_label, module):
        """Inicia el constructor de tipos"""
        self.models = dict()
        self.app_label = app_label
        self.module = module

    def get_model(self, obj):
        """Recupera o crea un modelo"""
        if not obj.pk:
            # creo el modelo en vacio para no dejarlo luego en
            # self.models[None], que da problemas.
            return self.create_model(obj)
        try:
            return self.models[obj.pk]
        except KeyError:
            return self.models.setdefault(obj.pk, self.create_model(obj))

    def create_model(self, obj):
        """Crea el modelo asociado a una instancia"""
        attrs = {'_id': models.IntegerField(primary_key=True)}
        attrs.update(dict((f.name, f.field) for f in obj.field_set.all()))
        attrs.update(dict((f.name, f.field) for f in obj.link_set.all()))
        if obj.parent:
            parent_model = obj.parent.model
            attrs['_up'] = models.ForeignKey(parent_model)
        return create_model(obj.modelname, self.app_label, self.module, attrs)

    def remove_model(self, instance):
        """Desvincula un modelo que va a ser modificado"""
        for obj in instance.__class__.objects.filter(parent=instance.pk):
            self.remove_model(obj)
        #for field in Link.objects.filter(related__table=instance.pk):
        #    self.remove_model(field.table)
        del(self.models[instance.pk])

    def __get__(self, instance, owner):
        """Recupera o crea un modelo"""
        if not owner:
            raise AttributeError(_('modelo'))
        return self.get_model(instance)

    def __set__(self, instance, value=None):
        """Actualiza un modelo"""
        if instance.pk:
            old_instance = instance.__class__.objects.get(pk=instance.pk)
            old_model = self.get_model(old_instance)
            self.remove_model(instance)
            assert(instance.pk not in self.models)
        else:
            old_model = old_instance = None
        if not value:
            delete_table(old_model)
        else:
            update_table(old_instance, old_model, instance)


class BaseField(models.Model):

    # esto lo dejo para las clases concretas que heredan de esta
    # table   = models.ForeignKey(Table, verbose_name=_('tabla'))

    name    = DBIdentifierField(verbose_name=_('nombre'))
    null    = models.BooleanField(verbose_name=_('NULL'))
    comment = models.CharField(max_length=254, blank=True,
                               verbose_name=_('comentario'))

    def sql(self):
        return sql_field(self.table.model, self.field)

    class Meta:
        abstract = True

    def __unicode__(self):
        return unicode(_("<%s> %s") % (unicode(self.table), self.name))


class TypedField(BaseField):

    def CharField(self):
        return models.CharField(max_length=self.len, default='',
                                blank=self.null, null=self.null)

    def IntegerField(self):
        return models.IntegerField(default=0,
                                   blank=self.null, null=self.null)

    def IPAddressField(self):
        return models.IPAddressField(default='',
                                     blank=self.null, null=self.null)

    @property
    def field(self):
        return getattr(self, str(self.kind))()

    @property
    def default(self):
        return getattr(self, '_Default_%s' % str(self.kind))

    _Default_CharField = ''
    _Default_IntegerField = 0
    _Default_IPAddressField = ''

    # no se puede tener una relacion con una clas abstracta
    kind    = models.CharField(max_length=32, verbose_name=_('tipo'),
                  choices=(
                      ('CharField',      _('texto')),
                      ('IntegerField',   _('numero')),
                      ('IPAddressField', _('IP')),
                ))

    # solo para los campos tipo CharField
    len     = BoundedIntegerField(1, 1024, verbose_name=_('longitud'),
                                  blank=True, null=True)

    class Meta:
        abstract = True

    @transaction.commit_on_success
    def save(self, *arg, **kw):
        old = None if not self.pk else self.__class__.objects.get(pk=self.pk)
        if not old and not self.null:
            # creo primero el campo como NULL, para que no se queje
            self.null = True
            update_field(self.table, old, self)
            super(TypedField, self).save(*arg, **kw)
            # preparo para reemplazar campo NOT NULL por NULL
            old = copy.copy(self)
            self.null = False
        if old and old.null and not self.null:
            # actualizo el modelo, por si esta desfasado.
            self.table.model = self.table
            fname = str(old.name)
            inval = self.table.model.objects.filter(**{fname: None})
            inval.update(**{fname: self.default})
        metafields = ['name', 'kind', 'null', 'len']
        changed = True if not old else any((getattr(old, x) != getattr(self, x))
                                           for x in metafields)
        if changed:
            # si ha cambiado algun campo que afecte a las metatablas
            # actualizo el SQL. Si no (por ejemplo, lo que ha cambiado es
            # el comment), no lo lanzo.
            self.table.model = self.table
            update_field(self.table, old, self)
        super(TypedField, self).save(*arg, **kw)
        # actualizo el modelo
        self.table.model = self.table

    @transaction.commit_on_success
    def delete(self, *arg, **kw):
        old = self.__class__.objects.get(pk=self.pk)
        delete_field(self.table, old) 
        super(TypedField, self).delete(*arg, **kw)
        # fuerzo una recarga del modelo
        self.table.model = self.table

