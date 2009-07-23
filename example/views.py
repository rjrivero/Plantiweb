#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.http import HttpResponse

from .meta import MetaClass
from .models import *


def show(request, steps):
    #root = MetaClass.data._type
    data = MetaClass.data
    result = []
    try:
        for step in (x for x in steps.split("/") if x):
            #result.append("BUSCANDO %s EN %s" % (step, str(root._Properties)))
            #root = root._Properties[step]._type
            result.append("BUSCANDO %s EN %s" % (step, str(data._type._Properties)))
            data = data[step]
        #for item in root.objects.all():
        for item in data:
            result.append(str(item))
    except AttributeError:
        pass
    return HttpResponse("".join(result))
