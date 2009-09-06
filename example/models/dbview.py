#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from django.db import models
from django.contrib.auth.models import User

from .dblog import app_label, ChangeLog
from .dbfields import *
from .dbmeta import Table


class View(models.Model):

    """MetaTabla que define las vistas de las tablas creadas"""

    name = models.CharField(max_length=64, verbose_name=_('nombre'))
    comment = models.CharField(max_length=240, verbose_name=_('descripcion'),
                               blank=True, null=True)

    class Meta:
        verbose_name = _('vista')
        verbose_name_plural = _('vistas')
        app_label = app_label

    def __unicode__(self):
        return self.name


class TableView(models.Model):

    """Metaclase que define las tablas accesibles en una vista"""

    view    = models.ForeignKey(View, verbose_name=_('vista'))
    table   = models.ForeignKey(Table, verbose_name=_('tabla'))
    summary = SeparatedValuesField(max_length=240, verbose_name=_('sumario'))
    fields  = SeparatedValuesField(max_length=240, verbose_name=_('campos'))

    class Meta:
        verbose_name = _('vista de tablas')
        verbose_name_plural = _('vistas de tablas')
        app_label = app_label
        unique_together = ('view', 'table')

    def __unicode__(self):
        return u"%s %s" % (self.view, self.table)


class UserView(models.Model):

    """Asigna una vista a un usuario"""

    user = models.ForeignKey(User, unique=True, verbose_name=_('usuario'))
    view = models.ForeignKey(View, verbose_name=_('vista'))

    class Meta:
        verbose_name = _('vista de usuario')
        verbose_name_plural = _('vistas de usuarios')
        app_label = app_label
        unique_together = ('user', 'view')


class Profile(object):

    """Filtra los atributos accesibles de un objeto"""

    def __init__(self, userview):
        try:
            if userview:
                self.view = userview.view.pk
            else:
                self.view = View.objects.get(name__iexact='Default').pk
        except View.DoesNotExist:
            self.view = None
        self.invalidate()

    def invalidate(self):
        self.version = ChangeLog.objects.current().pk
        self.fields = dict()
        self.summaries = dict()

    def _cached(self, d, pk, field):
        try:
            return d[pk] 
        except KeyError:
            try:
                item = TableView.get(view_id=self.view, table_id=pk)
            except (TableView.DoesNotExist):
                item = TokenTuple("")
            else:
                item = getattr(item, field)
            return d.setdefault(pk, item)

    def summary(self, model):
        return self._cached(self.summaries, model._DOMD.pk, 'summary')

    def fields(self, model):
        return self._cached(self.fields, model._DOMD.pk, 'fields')

