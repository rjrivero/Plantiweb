#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


try:
    import cPickle as pickle
except ImportError:
    import pickle
from gettext import gettext as _
from datetime import datetime

from django.db import models, connection

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


class PickledObject(str):

    """A subclass of string so it can be told whether a string is
       a pickled object or not (if the object is an instance of this class
       then it must [well, should] be a pickled one)."""

    pass


class PickledObjectField(models.Field):

    __metaclass__ = models.SubfieldBase

    def to_python(self, value):
        if isinstance(value, PickledObject):
            return pickle.loads(str(value))
        else:
            try:
                return pickle.loads(str(value))
            except:
                return value

    def get_db_prep_save(self, value):
        if value is not None and not isinstance(value, PickledObject):
            value = PickledObject(pickle.dumps(value))
        return value

    def get_internal_type(self): 
        return 'TextField'

    def get_db_prep_lookup(self, lookup_type, value):
        if lookup_type == 'exact':
            value = self.get_db_prep_save(value)
            return super(PickledObjectField, self).get_db_prep_lookup(
                       lookup_type, value)
        elif lookup_type == 'in':
            value = [self.get_db_prep_save(v) for v in value]
            return super(PickledObjectField, self).get_db_prep_lookup(
                       lookup_type, value)
        else:
            raise TypeError('Lookup type %s is not supported.' % lookup_type)


class ChangeLogManager(models.Manager):

    def current(self):
        try:
            return self.order_by('-id')[0]
        except IndexError:
            c = ChangeLog(sql="SELECT 'Cambio inicial'")
            c.save()
            return c


class ChangeLog(models.Model):

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

