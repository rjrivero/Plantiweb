#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from .models import Areas, Sedes, WANs
from django.contrib import admin

admin.site.register(Areas)
admin.site.register(Sedes)
admin.site.register(WANs)
