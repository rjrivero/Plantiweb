#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

from django import template

register = template.Library()


@register.filter(name='getattr')
def attrib(var, param):
    try:
        value = getattr(var, param)
        return unicode(value if value is not None else "")
    except (TypeError, AttributeError):
        return u""


@register.filter(name='getitem')
def item(var, param):
    try:
        value = var[param]
        return unicode(value if value is not None else "")
    except (TypeError, KeyError):
        return u""

