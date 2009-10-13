"""
settings for django-markitup

Time-stamp: <2009-03-18 11:54:09 carljm settings.py>

"""
from django.conf import settings

MARKITUP_PREVIEW_FILTER = getattr(settings, 'MARKITUP_PREVIEW_FILTER', None)
MARKITUP_SET = getattr(settings, 'MARKITUP_SET', 'markitup/sets/default')
MARKITUP_SKIN = getattr(settings, 'MARKITUP_SKIN', 'markitup/skins/simple')
JQUERY_URL = getattr(
    settings, 'JQUERY_URL',
    '/resources/js/dist/jquery.min.js')
