#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models

from plantillator.djread.djdata import *
from ..meta import MetaClass
from .root import Areas, Sedes
from .sede import Sede_Switches
    
    
class WANs(DJModel):

    __metaclass__ = MetaClass

    vlan = models.IntegerField()
    descripcion = models.CharField(max_length=200)
    password_ospf = models.CharField(max_length=32, blank=True, null=True)

    @relation(Areas, 'numero')
    def area(self, data):
        return data.areas

    @relation(Sedes, 'nombre')
    def sede_origen(self, data):
        return self.sedes

    @relation(Sede_Switches, 'nombre')
    def switch_origen(self, data):
        return data.sedes(nombre=self.sede_origen).switches

    ip_origen     = models.IPAddressField()
    puerto_origen = models.IntegerField()

    @relation(Sedes, 'nombre', blank=True, null=True)
    def sede_destino(self, data):
        return self.sedes

    @relation(Sede_Switches, 'nombre', blank=True, null=True)
    def switch_destino(self, data):
        return data.sedes(nombre=self.sede_destino).switches

    ip_destino     = models.IPAddressField(null=True, blank=True)
    puerto_destino = models.IntegerField(null=True, blank=True)

    def __unicode__(self):
        return "VLAN %d (%s)" % (self.vlan, self.descripcion)

    class Meta:
        app_label = 'example'

    class DOMD:
        summary = 'vlan, descripcion, sede_origen, sede_destino'.split(', ')
