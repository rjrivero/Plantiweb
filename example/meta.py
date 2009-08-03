#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models

from plantillator.data.dataobject import DataType
from plantillator.djread.meta import MetaData, RootData


class MetaClass(models.Model.__metaclass__):

    """MetaClase que convierte los modelos en DataObjects

    Hay que crear una clase por cada applicacion. Intentar hacerlo
    con un"generador de clases" (una funcion que devuelva una clase
    personalizada) es un problema porque se ejecuta cada vez que
    alguien importa el modulo, lo que hace que se tengan varias
    copias de la MetaClase y sus respectivos atributos (data, root).
    """

    data = RootData()
    root = data._type

    def __new__(cls, n, b, d):
        cls = super(MetaClass, cls).__new__(cls, n, b, d)
        setattr(cls, '_DOMD', MetaData(cls, n, b, d, MetaClass.data))
        return cls

