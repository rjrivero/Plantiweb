#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from .models import Table, Field, Link, Dynamic, RevisionLog, ChangeLog
from django.contrib import admin


class FieldInline(admin.TabularInline):
    model = Field
    extra = 4


class LinkInline(admin.TabularInline):
    model = Link
    extra = 1


class TableAdmin(admin.ModelAdmin):
    list_display = ['fullname', 'name', 'parent']
    fields  = ['name', 'parent', 'comment']
    inlines = [FieldInline, LinkInline]
    ordering = ['parent']


class LinkAdmin(admin.ModelAdmin):
    list_display = ['table', 'name', 'related', 'null']
    fields = ['table', 'name', 'comment', 'null', 'related', 'filter']
    ordering = ['table']


class DynamicAdmin(admin.ModelAdmin):
    list_display = ['related', 'code']
    ordering = ['related']


class RevisionLogAdmin(admin.ModelAdmin):
    list_display = ['stamp', 'major', 'minor', 'rev', 'summary']
    list_filter = ['stamp']


class ChangeLogAdmin(admin.ModelAdmin):
    list_display = ['stamp', 'id', 'major', 'minor', 'rev', 'sql']
    list_filter = ['stamp']


admin.site.register(Table, TableAdmin)
admin.site.register(Link, LinkAdmin)
admin.site.register(Dynamic, DynamicAdmin)
admin.site.register(RevisionLog, RevisionLogAdmin)
admin.site.register(ChangeLog, ChangeLogAdmin)

