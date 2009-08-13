#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from django.db import models

from .dbmeta import DBIdentifierField, Table
from .dblog import app_label


class TokenTuple(tuple):

    def __new__(cls, token, value):
        if not hasattr(value, '__iter__'):
            value = tuple(x.strip() for x in value.split(token))
        if any(x for x in value if not DBIdentifierField._VALID.match(x)):
            raise ValueError(value)
        obj = tuple.__new__(cls, value)
        obj.token = token
        return obj

    def __unicode__(self):
        return self.token.join(self)

    def __str__(self):
        return str(unicode(self))


class SeparatedValuesField(models.CharField):

    __metaclass__ = models.SubfieldBase
 
    def __init__(self, *args, **kwargs):
        self.token = unicode(kwargs.pop('token', ','))
        super(SeparatedValuesField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        return TokenTuple(self.token, value)

    def get_db_prep_value(self, value):
        return unicode(TokenTuple(self.token, value))
 

class View(models.Model):

    """MetaTabla que define las vistas de las tablas creadas"""

    name = models.CharField(max_length=64, verbose_name=_('nombre'))

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
        verbose_name = _('vista de tabla')
        verbose_name_plural = _('vistas de tabla')
        app_label = app_label
        unique_together = ('view', 'table')

    def __unicode__(self):
        return u"%s %s" % (self.view, self.table)

