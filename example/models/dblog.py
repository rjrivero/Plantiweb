#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from datetime import datetime
from cPickle import dumps
from base64 import encodestring

from django.db import models

app_label = 'example'


class RevisionManager(models.Manager):

    def current(self):
        return self.order_by('-major', '-minor', '-rev')[0]

   
class RevisionLog(models.Model):

    major = models.IntegerField()
    minor = models.IntegerField()
    rev   = models.IntegerField()
    stamp = models.DateTimeField(default=datetime.now)
    summary = models.CharField(max_length=200)

    objects = RevisionManager()

    class Meta:
        ordering = ['-major', '-minor', '-rev']
        verbose_name = _('revision')
        verbose_name_plural = _('revisiones')
        app_label = app_label
        unique_together = ['major', 'minor', 'rev']

    def __unicode__(self):
        return u"%d.%d.%d [%s] (%s)" % (self.major, self.minor, self.rev,
                                        self.stamp, self.summary)


class ChangeLogManager(models.Manager):

    def current(self):
        try:
            return self.order_by('-id')[0]
        except IndexError:
            c = ChangeLog()
            c.log(_('Cambio inicial'))
            return c


class ChangeLog(models.Model):

    major  = models.IntegerField()
    minor  = models.IntegerField()
    rev    = models.IntegerField()
    stamp  = models.DateTimeField(default=datetime.now)
    sql    = models.TextField()
    params = models.CharField(max_length=240, blank=True, null=True)

    objects = ChangeLogManager()

    def log(self, sql, params=None):
        current     = RevisionLog.objects.current()
        self.major  = current.major
        self.minor  = current.minor
        self.rev    = current.rev
        self.sql    = sql
        self.params = encodestring(dumps(params)) if params else None
        self.save()
        return (sql, params)

    class Meta:
        verbose_name = _('cambio')
        verbose_name_plural = _('cambios')
        ordering = ['-stamp', '-id']
        app_label = app_label

    def __unicode__(self):
        return u"%d.%d.%d [%s] (%s)" % (self.major, self.minor, self.rev,
                                        self.stamp, self.sql)

