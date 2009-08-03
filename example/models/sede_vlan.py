#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models

from plantillator.djread.djdata import *
from ..meta import MetaClass
from .sede import Sede_Vlans, Sede_Switches
    
    
class Sede_Vlan_Vlans(DJModel):

    __metaclass__ = MetaClass

    _up        = childOf(Sede_Vlans)
    numero     = models.IntegerField()
    nombre     = models.CharField(max_length=32)
    rango      = models.CharField(max_length=32, null=True, blank=True)
    dhcp_relay = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        if not self.descripcion:
            return self.nombre
        return "VLAN %d (%s)" % (self.numero, self.nombre)

    class Meta:
        app_label = 'example'

    class DOMD:
        summary = 'numero, nombre, rango, dhcp_relay'.split(', ')


class Sede_Vlan_Switches(DJModel):

    __metaclass__ = MetaClass

    _up     = childOf(Sede_Vlans)

    @relation(Sede_Switches, 'nombre')
    def switch(self, data):
        return self.up.up.switches

    ip      = models.IPAddressField(blank=True, null=True)
    accesos = models.CharField(max_length=200, null=True, blank=True)
    uplinks = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        if not self.ip:
            return self.switch
        return "%s (%s)" % (self.switch, self. ip)

    class Meta:
        app_label = 'example'

    class DOMD:
        summary = 'ip, accesos, uplinks'.split(', ')
