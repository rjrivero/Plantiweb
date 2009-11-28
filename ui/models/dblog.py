#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from datetime import datetime
from django.db import models, connection

from .dbfields import PickledObjectField


app_label = 'ui'


class RevisionManager(models.Manager):

    """Gestor de revisiones"""

    def current(self):
        try:
            return self.order_by('-major', '-minor', '-rev')[0]
        except IndexError:
            new = RevisionLog(major=0, minor=0, rev=1)
            new.summary = _("Revision inicial")
            new.save()
            return new


class RevisionLog(models.Model):

    """Listado de revisiones por las que ha pasado la base de datos"""

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

    """Gestor de modificaciones de metadatos"""

    def current(self):
        try:
            return self.order_by('-id')[0]
        except IndexError:
            c = ChangeLog(sql="SELECT 'Cambio inicial'")
            c.save()
            return c


class ChangeLog(models.Model):

    """Listado de modificaciones hechas a los metadatos de la aplicacion"""

    major  = models.IntegerField(blank=True)
    minor  = models.IntegerField(blank=True)
    rev    = models.IntegerField(blank=True)
    stamp  = models.DateTimeField(default=datetime.now)
    sql    = models.TextField()
    params = PickledObjectField(blank=True, null=True)

    objects = ChangeLogManager()

    def __init__(self, *arg, **kw):
        try:
            self.cursor = kw.pop('cursor')
        except KeyError:
            self.cursor = None
        super(ChangeLog, self).__init__(*arg, **kw)

    def save(self):
        """Etiqueta el objeto con la revision actuall y lo salva"""
        current     = RevisionLog.objects.current()
        self.major  = current.major
        self.minor  = current.minor
        self.rev    = current.rev
        super(ChangeLog, self).save()
        cursor = self.cursor or connection.cursor()
        cursor.execute(self.sql, self.params or tuple())

    class Meta:
        verbose_name = _('cambio')
        verbose_name_plural = _('cambios')
        ordering = ['-stamp', '-id']
        app_label = app_label

    def __unicode__(self):
        return u"%d.%d.%d [%s] (%s)" % (self.major, self.minor, self.rev,
                                        self.stamp, self.sql)

