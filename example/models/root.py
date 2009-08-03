#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models

from plantillator.djread.djdata import *
from ..meta import MetaClass


class Areas(DJModel):

    __metaclass__ = MetaClass

    numero      = anchor(models.IntegerField)
    nombre      = models.CharField(max_length=32)
    descripcion = models.CharField(max_length=200, null=True, blank=True)
    tipo        = models.CharField(max_length=32, null=True, blank=True,
                            choices=(
                                ("stub", "Stub"),
                                ("stub no summary", "Totally Stubby"),
                                ("nssa", "Not-so-stubby")))
    rango       = models.CharField(max_length=32, null=True, blank=True)

    def __unicode__(self):
        return "Area %d (%s)" % (self.numero, self.nombre)

    class Meta:
        app_label = 'example'

    class DOMD:
        summary = 'numero, nombre, descripcion, tipo, rango'.split(', ')


class Sedes(DJModel):

    __metaclass__ = MetaClass

    nombre      = anchor(models.CharField, max_length=32)
    descripcion = models.CharField(max_length=200, null=True, blank=True)
    password    = models.CharField(max_length=32, null=True, blank=True)

    @relation(Areas, 'numero')
    def area(self, data):
        return data.areas

    def __unicode__(self):
        return "%s (%s)" % (self.nombre, self.descripcion)

    class Meta:
        app_label = 'example'

    class DOMD:
        summary = 'nombre, descripcion, area'.split(', ')

