#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models

from plantillator.data.dataobject import RootType
from plantillator.data.meta import extend, django_prop
    
    
class MetaClass(models.Model.__metaclass__):

    """MetaClase que convierte los modelos en DataObjects

    Hay que crear una clase por cada applicacion. Intentar hacerlo
    con un"generador de clases" (una funcion que devuelva una clase
    personalizada) es un problema porque se ejecuta cada vez que
    alguien importa el modulo, lo que hace que se tengan varias
    copias de la MetaClase y sus respectivos atributos (data, root).
    """

    root = RootType(django_prop)
    data = root()

    def __new__(cls, name, bases, d):
        cls = models.Model.__metaclass__.__new__(cls, name, bases, d)
        return extend(cls, name, bases, d, MetaClass.data)
