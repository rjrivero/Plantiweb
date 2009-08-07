#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from itertools import chain
import copy

from django.db import models, transaction, connection
from django.core.management import sql, color


def create_model(name, app_label, module, attrs=None):
    """Crea un modelo sin base de datos detras"""
    class Meta:
        pass
    setattr(Meta, 'app_label', app_label)
    attrs = attrs or dict()
    attrs.update({'Meta': Meta, '__module__': module})
    return type(str(name), (models.Model,), attrs)


def sql_model(model, known=None):
    """Genera el codigo SQL necesario para crear la tabla de un modelo"""
    style = color.no_style()
    return connection.creation.sql_create_model(model, style, known)[0][0]


def sql_field(model, name, field):
    """Genera el codigo SQL necesario para crear un campo de una tabla"""
    model = create_model('test', model._meta.app_label, model.__module__,
                {name: field})
    sql   = sql_model(model).split("\n")[2].strip()
    print "SQL DEL CAMPO: %s" % sql
    return sql


def delete_table(model):
    """Borra una tabla de la base de datos"""
    sql = "DROP TABLE %s" % str(model._meta.db_table)
    connection.cursor().execute(sql)


def update_table(old_instance, old_model, current_instance):
    """Actualiza o modifica una tabla de la base de datos"""
    if not old_instance:
        sql = current_instance.sql()
        connection.cursor().execute(sql)
    elif old_instance.name != current_instance.name:
        sql = ("ALTER TABLE %s RENAME TO %s" %
                  (old_model._meta.db_table,
                   current_instance.model._meta.db_table))
        connection.cursor().execute(sql)


def delete_field(table, field):
    """Borra un campo de una tabla"""
    sql = "ALTER TABLE %s DROP COLUMN %s" % (
          str(table.model._meta.db_table), str(field.name))
    connection.cursor().execute(sql)


def update_field(table, old_instance, current_instance):
    """Actualiza o modifica un campo de una tabla de la base de datos"""
    tnm = table.model._meta.db_table
    sql = sql_field(current_instance.table.model,
                    current_instance.name,
                    current_instance.field)
    statements = list()
    if not old_instance:
        statements.append("ALTER TABLE %s ADD %s" % (tnm, sql))
    else:
        if old_instance.name != current_instance.name:
            statements.append("ALTER TABLE %s RENAME COLUMN %s TO %s" % (
                tnm, old_instance.name, current_instance.name))
        statements.append("ALTER TABLE %s MODIFY %s" % (tnm, sql))
    cursor = connection.cursor()
    for sql in statements:
        cursor.execute(sql)


class ModelDescriptor(object):

    def __init__(self, app_label, module):
        """Inicia el constructor de tipos"""
        self.models = dict()
        self.app_label = app_label
        self.module = module

    def get_model(self, obj):
        """Recupera o crea un modelo"""
        try:
            model = self.models[obj.pk]
        except KeyError:
            model = self.models.setdefault(obj.pk, self.create_model(obj))
        return model

    def create_model(self, obj):
        """Crea el modelo asociado a una instancia"""
        attrs = dict((f.name, f.field) for f in obj.field_set.all())
        attrs.update(dict((f.name, f.field) for f in obj.link_set.all()))
        if obj.parent:
            parent_model = obj.parent.model
            attrs['_up'] = models.ForeignKey(parent_model)
        return create_model(obj.modelname, self.app_label, self.module, attrs)

    def remove_model(self, instance):
        """Desvincula un modelo que va a ser modificado"""
        for obj in Table.objects.filter(parent=instance.pk):
            self.remove_model(obj)
        for field in Link.objects.filter(related__table=instance.pk):
            self.remove_model(field.table)
        del(self.models[instance.pk])

    def __get__(self, instance, owner):
        """Recupera o crea un modelo"""
        if not owner:
            raise AttributeError(_('modelo'))
        return self.get_model(instance)

    def __set__(self, instance, value=None):
        """Actualiza un modelo"""
        if instance.pk:
            old_instance = Table.objects.get(pk=instance.pk)
            old_model = self.get_model(old_instance)
            self.remove_model(instance)
        else:
            old_model = old_instance = None
        if not value:
            delete_table(old_model)
        else:
            update_table(old_instance, old_model, instance)


class Table(models.Model):

    parent  = models.ForeignKey('self', verbose_name=_('subtabla de'),
                blank=True, null=True)
    name    = models.CharField(max_length=16, verbose_name=_('nombre'))
    comment = models.TextField(blank=True, verbose_name=_('comentario'))

    def path(self):
        if not self.parent:
            return (self,)
        return chain(self.parent.path(), (self,))

    @property
    def modelname(self):
        return '_'.join(str(x.name).capitalize() for x in self.path())

    @property
    def fullname(self):
        return u".".join(x.name for x in self.path())

    model = ModelDescriptor('example', __name__)
    
    def sql(self):
       return sql_model(self.model, set(self.path()))

    def __unicode__(self):
        return self.fullname

    class Meta:
        verbose_name = _('Tabla')
        verbose_name_plural = _('Tablas')

    @transaction.commit_on_success
    def save(self, *arg, **kw):
        # tengo que hacer el cambio antes de actualizar la bd, porque
        # en otro caso, no tendria disponible el antiguo valor.
        self.model = self
        super(Table, self).save(*arg, **kw)

    @transaction.commit_on_success
    def delete(self, *arg, **kw):
        self.model = None
        super(Table, self).delete(*arg, **kw)


class BaseField(models.Model):

    table   = models.ForeignKey(Table, verbose_name=_('tabla'))
    name    = models.CharField(max_length=16, verbose_name=_('nombre'))
    null    = models.BooleanField(verbose_name=_('NULL'))
    comment = models.CharField(max_length=254, blank=True,
                               verbose_name=_('comentario'))

    def sql(self):
        return field_sql(self.table.model, self.field)

    class Meta:
        abstract = True

    def __unicode__(self):
        return unicode(_("<%s> %s") % (unicode(self.table), self.name))


class TypedField(BaseField):

    def CharField(self):
        return models.CharField(max_length=self.len, default='',
                                blank=self.null, null=self.null)

    def IntegerField(self):
        return models.IntegerField(default=0,
                                   blank=self.null, null=self.null)

    def IPAddressField(self):
        return models.IPAddressField(default='',
                                     blank=self.null, null=self.null)

    @property
    def field(self):
        return getattr(self, str(self.kind))()

    # no se puede tener una relacion con una clas abstracta
    kind    = models.CharField(max_length=32, verbose_name=_('tipo'),
                  choices=(
                      ('CharField',      _('texto')),
                      ('IntegerField',   _('numero')),
                      ('IPAddressField', _('IP')),
                ))

    # solo para los campos tipo CharField
    len     = models.IntegerField(verbose_name=_('longitud'),
                                  blank=True, null=True)

    class Meta:
        abstract = True

    @transaction.commit_on_success
    def save(self, *arg, **kw):
        old = None if not self.pk else self.__class__.objects.get(pk=self.pk)
        if not old and not self.null:
            # creo primero el campo como NULL, para que no se queje
            self.null = True
            update_field(self.table, old, self)
            super(TypedField, self).save(*arg, **kw)
            # preparo para reemplazar campo NOT NULL por NULL
            old = copy.copy(self)
            self.null = False
            # actualizo el modeloa
            self.table.model = self.table
        if old and old.null and not self.null:
            self.table.model.objects.all().update(**{str(old.name): ''})
        update_field(self.table, old, self)
        super(TypedField, self).save(*arg, **kw)
        # actualizo el modelo
        self.table.model = self.table

    @transaction.commit_on_success
    def delete(self, *arg, **kw):
        old = self.__class__.objects.get(pk=self.pk)
        delete_field(self.table, old) 
        super(TypedField, self).delete(*arg, **kw)
        # fuerzo una recarga del modelo
        self.table.model = self.table


class Field(TypedField):

    class Meta:
        verbose_name = _('campo de datos')
        verbose_name_plural = _('campos de datos')


class Link(BaseField):

    # solo para los campos tipo Related
    related = models.ForeignKey(Field, verbose_name=_('ligado a'),
                blank=True, null=True)

    filter  = models.TextField(verbose_name=_('filtro'))

    @property
    def field(self):
        other = copy.copy(self.related)
        other.null = instance.null
        return other.field

    class Meta:
        verbose_name = _('campo de enlace')
        verbose_name_plural = _('campos de enlace')


class Dynamic(models.Model):

    # solo para los campos de tipo Dynamic
    related = models.OneToOneField(Field, verbose_name=_('ligado a'))
    code = models.TextField(verbose_name=_('codigo'))

    class Meta:
        verbose_name = _('campo dinamico')
        verbose_name_plural = _('campos dinamicos')

    def __unicode__(self):
        return unicode(_('codigo de %s') % str(self.related))

    @transaction.commit_on_success
    def save(self, *arg, **kw):
        super(Dynamic, self).save(*arg, **kw)
        # fuerzo una recarga del modelo
        table = self.related.table
        table.model = table

    @transaction.commit_on_success
    def delete(self, *arg, **kw):
        super(Dynamic, self).delete(*arg, **kw)
        # fuerzo una recarga del modelo
        table = self.related.table
        table.model = table

