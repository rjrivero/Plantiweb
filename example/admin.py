#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from .models import Table, Field, Link, Dynamic
from django.contrib import admin


class FieldInline(admin.TabularInline):
    model = Field
    extra = 2

class TableAdmin(admin.ModelAdmin):
    list_display = ['fullname', 'name', 'parent']
    fields  = ['name', 'parent', 'comment']
    inlines = [FieldInline]
    ordering = ['parent']

class LinkAdmin(admin.ModelAdmin):
    list_display = ['table', 'name', 'related', 'null']
    ordering = ['table']

class DynamicAdmin(admin.ModelAdmin):
    list_display = ['related', 'code']
    ordering = ['related']


admin.site.register(Table, TableAdmin)
admin.site.register(Link, LinkAdmin)
admin.site.register(Dynamic, DynamicAdmin)
