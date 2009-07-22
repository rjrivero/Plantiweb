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
    descripcion = models.CharField(max_length=200)
    area = Relation(Areas)
    desde = Relation(Switches, related_name='wans_from_set')
    hasta = Relation(Switches, related_name='wans_to_set')
    ip1 = models.IPAddressField()
    puerto1 = models.IntegerField()
    ip2 = models.IPAddressField(null=True, blank=True)
    puerto2 = models.IntegerField(null=True, blank=True)
    password_ospf = models.CharField(max_length=32, blank=True, null=True)

    def __unicode__(self):
        return "VLAN %d (%s)" % (self.vlan, self.descripcion)

    class Meta:
        app_label = 'example'
        db_table = 'wans'
