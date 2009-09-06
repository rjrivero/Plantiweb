#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from django.contrib import admin
from .models import *


class FieldInline(admin.TabularInline):
    model = Field
    extra = 4


class LinkInline(admin.TabularInline):
    model = Link
    extra = 2


class TableViewInline(admin.TabularInline):
    model = TableView
    extra = 4


class UserViewInline(admin.TabularInline):
    model = UserView
    extra = 4


class TableAdmin(admin.ModelAdmin):
    list_display = ['fullname', 'name', 'parent']
    fields  = ['name', 'parent', 'comment']
    inlines = [FieldInline, LinkInline]
    ordering = ['parent']


#class LinkAdmin(admin.ModelAdmin):
#    list_display = ['table', 'name', 'related', 'null']
#    fields = ['table', 'name', 'comment', 'null', 'related', 'filter']
#    ordering = ['table']


class DynamicAdmin(admin.ModelAdmin):
    list_display = ['related', 'code']
    ordering = ['related']


class RevisionLogAdmin(admin.ModelAdmin):
    list_display = ['stamp', 'major', 'minor', 'rev', 'summary']
    list_filter = ['stamp']


class ChangeLogAdmin(admin.ModelAdmin):
    list_display = ['stamp', 'id', 'major', 'minor', 'rev', 'sql']
    list_filter = ['stamp']


class ViewAdmin(admin.ModelAdmin):
    list_display = ['name', 'comment']
    inlines = [TableViewInline, UserViewInline]


admin.site.register(Table, TableAdmin)
#admin.site.register(Link, LinkAdmin)
admin.site.register(Dynamic, DynamicAdmin)
admin.site.register(RevisionLog, RevisionLogAdmin)
admin.site.register(ChangeLog, ChangeLogAdmin)
admin.site.register(View, ViewAdmin)

