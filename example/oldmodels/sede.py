#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models

from plantillator.djread.djdata import *
from ..meta import MetaClass
from .root import Sedes
    
    
class Sede_Switches(DJModel):

    __metaclass__ = MetaClass

    _up         = childOf(Sedes)
    nombre      = anchor(models.CharField, max_length=32)
    descripcion = models.CharField(max_length=200, null=True, blank=True)
    password    = models.CharField(max_length=32, null=True, blank=True)
    loopback    = models.IPAddressField(null=True, blank=True)

    def __unicode__(self):
        if not self.descripcion:
            return self.nombre
        return "%s (%s)" % (self.nombre, self. descripcion)

    class Meta:
        app_label = 'example'

    class DOMD:
        summary = 'nombre, descripcion, loopback'.split(', ')


class Sede_Vlans(DJModel):

    __metaclass__ = MetaClass

    _up         = childOf(Sedes)
    nombre      = models.CharField(max_length=32)
    descripcion = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        if not self.descripcion:
            return self.nombre
        return "%s (%s)" % (self.nombre, self. descripcion)

    class Meta:
        app_label = 'example'

    class DOMD:
        summary = 'nombre, descripcion'.split(', ')
