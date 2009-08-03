#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models

from plantillator.djread.djdata import *
from ..meta import MetaClass
from .sede import Sede_Switches
    
    
class Sede_Switch_Puertos(DJModel):

    __metaclass__ = MetaClass

    _up        = childOf(Sede_Switches)
    interfaces = models.CharField(max_length=200)
    medio      = models.CharField(max_length=32, choices=(
        ("fiber", "Fibra"),
        ("copper", "Cobre")
        ), null=True, blank=True)
    velocidad  = models.IntegerField(choices=(
        (10, "10"), (100, "100"), (1000, "1000")),
                                    null=True, blank=True)
    modo       = models.CharField(max_length=32, choices=(
        ("half", "Hal-Duplex"), ("full", "Full-Duplex")),
                            null=True, blank=True)

    def __unicode__(self):
        return self.interfaces

    class Meta:
        app_label = 'example'

    class DOMD:
        summary = 'interfaces, medio, velocidad, modo'.split(', ')
