#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
import re
import copy

from django.db import models, transaction

from .dbraw import create_model


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
        try:
            del(self.models[instance.pk])
        except KeyError:
            pass

    def __get__(self, instance, owner):
        """Recupera o crea un modelo"""
        if not owner:
            raise AttributeError(_('modelo'))
        return self.get_model(instance)

    def __set__(self, instance, value=None):
        """Elimina la cache de un modelo"""
        if instance.pk:
            self.remove_model(instance)

