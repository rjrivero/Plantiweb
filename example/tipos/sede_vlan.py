#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models

from plantillator.data.meta import Relation, dynamic
from ..meta import MetaClass
from .sede import Vlans as Sede_Vlans
from .sede import Switches as Sede_Switches
    
    
class Vlans(models.Model):

    __metaclass__ = MetaClass

    _up = Relation(Sede_Vlans)
    numero = models.IntegerField
    nombre = models.CharField(max_length=32)
    rango = models.CharField(max_length=32, null=True, blank=True)
    dhcp_relay = models.CharField(max_length=200, null=True, blank=True)


    def __unicode__(self):
        if not self.descripcion:
            return self.nombre
        return "VLAN %d (%s)" % (self.numero, self.nombre)


class Switches(models.Model):

    __metaclass__ = MetaClass

    _up = Relation(Sede_Vlans)
    switch = Relation(Sede_Switches)
    ip = models.IPAddressField(blank=True, null=True)
    accesos = models.CharField(max_length=200, null=True, blank=True)
    uplinks = models.CharField(max_length=200, null=True, blank=True)

    def __unicode__(self):
        if not self.ip:
            return str(self.switch)
        return "%s (%s)" % (str(self.switch), self. ip)
