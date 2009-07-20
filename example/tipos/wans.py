#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models

from plantillator.data.meta import Relation, dynamic
from ..meta import MetaClass
from .root import Areas
from .sede import Switches
    
    
class WANs(models.Model):

    __metaclass__ = MetaClass

    vlan = models.IntegerField()
    descripcion = models.charField(max_length=200)
    area = Relation(Areas)
    desde = Relation(Switches)
    hasta = Relation(Switches, blank=True, null=True)
    ip1 = models.IPAddressField()
    puerto1 = models.IntegerField()
    ip2 = IPAddressField(null=True, blank=True)
    puerto2 = models.IntegerField(null=True, blank=True)
    password_ospf = models.CharField(max_length=32, blank=True, null=True)

    def __unicode__(self):
        return "VLAN %d (%s)" % (self.vlan, self.descripcion)
