#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models

from plantillator.data.meta import Relation, dynamic
from ..meta import MetaClass


class Areas(models.Model):

    __metaclass__ = MetaClass

    numero = models.IntegerField()
    nombre = models.CharField(max_length=32)
    descripcion = models.CharField(max_length=200, null=True, blank=True)
    tipo = models.CharField(max_length=32, null=True, blank=True,
                            choices=(
                                ("stub", "Stub"),
                                ("stub no summary", "Totally Stubby"),
                                ("nssa", "Not-so-stubby")))
    rango = models.charfield(max_length=32, null=True, blank=True)

    def __unicode__(self):
        return "Area %d (%s)" % (self.numero, self.nombre)


class Sedes(models.Model):

    __metaclass__ = MetaClass

    nombre = models.CharField(max_length=32)
    descripcion = models.CharField(max_length=200, null=True, blank=True)
    area = Relation(Areas)
    password = models.CharField(max_length=32, null=True, blank=True)

    def __unicode__(self):
        return "%s (%s)" % (self.nombre, self.descripcion)
