#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from copy import copy 

from django.db import models, connection
from django.core.management import sql, color
# HACKISH - HACKISH - HACKISH
from django.db.models.loading import cache

from .dblog import ChangeLog


# Posibles tipos de indice
NO_INDEX       = 0
UNIQUE_INDEX   = 1
MULTIPLE_INDEX = 2


def create_model(name, app_label, module, attrs=None, bases=(models.Model,)):
    """Crea un modelo dinamicamente"""
    class Meta:
        pass
    setattr(Meta, 'app_label', app_label)
    setattr(Meta, 'db_table', '%s_%s' % (app_label, name))
    attrs = attrs or dict()
    attrs.update({'Meta': Meta, '__module__': module})
    # HACKISH - HACKISH - HACKISH
    #
    # Django guarda una cache de modelos, y cuando se intenta crear uno que ya
    # esta en cache, en vez de actualizar la cache con el modelo nuevo, devuelve
    # el modelo antiguo.
    #
    # Esto es muy malo para nuestros propositos, asi que a continuacion pongo
    # un hack que elimina el modelo de la cache, si existia
    app_cache = cache.app_models.get(app_label, dict())
    try:
        del(app_cache[name.lower()])
    except KeyError:
        pass
    # Ahora ya puedo crear el modelo
    return type(name, bases, attrs)


def sql_add_model(model, known=None):
    """Genera el codigo SQL necesario para crear la tabla de un modelo"""
    style, c = color.no_style(), connection.creation
    sql, deps = c.sql_create_model(model, style, known)
    sql.extend(c.sql_indexes_for_model(model, style))
    for model in deps.keys():
        sql.extend(c.sql_for_pending_references(model, style, deps))
    return sql


def sql_add_foreign_key(model, known=None):
    """Genera el codigo SQL para las FK de un modelo"""
    style, c = color.no_style(), connection.creation
    dummy, deps = c.sql_create_model(model, style, known)
    sql = list()
    for model in deps.keys():
        sql.extend(c.sql_for_pending_references(model, style, deps))
    return sql


def sql_drop_model(model):
    """Genera el codigo SQL para eliminar un modelo"""
    style, c = color.no_style(), connection.creation
    refs = dict()
    for field in (f for f in model._meta.local_fields if f.rel):
        refs.setdefault(field.rel.to, []).append((model, field))
    return c.sql_destroy_model(model, refs, style)


def sql_drop_foreign_key(model):
    """Genera el codigo SQL para eliminar las FK de un modelo"""
    style,c = color.no_style(), connection.creation
    sql, refs = list(), dict()
    for field in (f for f in model._meta.local_fields if f.rel):
        refs.setdefault(field.rel.to, []).append((model, field))
    for model in refs.keys():
        sql.extend(c.sql_remove_table_constraints(model, refs, style))
    return sql


def sql_inline_field(model, name, field):
    """Genera el codigo SQL necesario para definir un campo"""
    # HACKISH
    # El campo que creamos esta en la segunda linea del SQL (la primera es el
    # CREATE TABLE, la segunda la clave primaria)
    testtype = create_model("test", model._meta.app_label, model.__module__,
                {name: field})
    return sql_add_model(testtype)[0].split("\n")[2].strip()


def sql_add_field(model, name, field):
    """Genera el codigo SQL para agregar un campo a una tabla"""
    inline = sql_inline_field(model, name, field)
    sql = ["ALTER TABLE %s ADD %s" % (model._meta.db_table, inline)]
    # Ya no gestionamos los indices con django, sino con SQL.
    #if field.db_index:
    #    sql.extend(sql_add_index(model, name, field))
    return sql


def sql_drop_field(model, name):
    """Genera el codigo SQL para eliminar un campo de una tabla"""
    return ["ALTER TABLE %s DROP %s" % (model._meta.db_table, name)]


def sql_rename_model(old_model, new_model):
    """Genera el codigo SQL para renombrar una tabla"""
    old, new = old_model._meta.db_table, new_model._meta.db_table
    statements = sql_drop_foreign_key(old_model)
    if old != new:
        statements.append("ALTER TABLE %s RENAME TO %s" % (old, new))
    statements.extend(sql_add_foreign_key(new_model))
    return statements


def sql_rename_field(model, old_name, new_name, field):
    """Genera el codigo SQL para renombrar un campo de una tabla"""
    tname, old, new = model._meta.db_table, old_name, new_name
    sql = sql_inline_field(model, new_name, field)
    return ["ALTER TABLE %s CHANGE COLUMN %s %s" % (tname, old, sql)]


def sql_add_index(model, name, idxname):
    """Genera el codigo SQL para indexar un campo"""
    #style, c = color.no_style(), connection.creation
    #return c.sql_indexes_for_field(model, field, style)
    table = model._meta.db_table
    return ["ALTER TABLE %s ADD INDEX %s (%s)" % (
                table, idxname, name)]


def sql_drop_index(model, name, idxname):
    """Genera el codigo SQL para indexar un campo"""
    table = model._meta.db_table
    return ["ALTER TABLE %s DROP INDEX %s" % (
                table, idxname)]


def sql_add_unique(model, name, idxname):
    table = model._meta.db_table
    return ["ALTER TABLE %s ADD UNIQUE INDEX %s (%s)" % (
                table, idxname, name)]


def sql_modify_field(model, name, field):
    """Genera el codigo SQL para modificar un campo de una tabla"""
    inline = sql_inline_field(model, name, field)
    return ["ALTER TABLE %s MODIFY %s" % (model._meta.db_table, inline)]


def sql_update_null(model, name, field, defval):
    """Genera el codigo SQL para actualizar los elementos NULL de un campo"""
    clean = [field.get_db_prep_value(defval)]
    table = model._meta.db_table
    return [("UPDATE %s SET %s=%%s WHERE %s IS NULL" % (table, name, name), clean)]



def execute(query_list):
    """Ejecuta una serie de consultas SQL.

    Cada consulta puede ser bien un texto, o bien una tupla(sql, parametros).
    """
    cursor = connection.cursor()
    for query in query_list:
        sql, params = query, None
        if hasattr(query, '__iter__'):
            sql, params = query
        # al salvar, tambien se ejecuta la query
        ChangeLog(cursor=cursor, sql=sql, params=params).save()


def delete_table(instance):
    """Borra una tabla de la base de datos"""
    execute(sql_drop_model(instance.model))


def update_table(old_instance, cur_instance, recurring=False):
    """Actualiza o modifica una tabla de la base de datos"""
    if not old_instance:
        statements = sql_add_model(cur_instance.model)
    else:
        statements = list()
        # si cambia la tabla padre, o cambia el nombre de la tabla, hay que
        # eliminar las foreign keys antiguas y recrearlas, porque django le pone
        # a cada CONSTRAINT un sufijo que depende del nombre del modelo, y si
        # lo cambiamos sin alterar las referencias, le perderiamos la pista.
        op = old_instance.parent.pk if old_instance.parent else None 
        np = cur_instance.parent.pk if cur_instance.parent else None
        if recurring or op != np or old_instance.name != cur_instance.name:
            children = list(old_instance.table_set.all())
            for child in children:
                # obligo a que reconstruyan el model con el parent anterior
                child.model, child.parent = None, old_instance
                model = child.model
            oldm, newm = old_instance.model, cur_instance.model
            if op is None and np is not None:
                # La tabla que se habia creado no tenia campo _up_id porque su
                # modelo no tenia clave primaria. Tengo que modificar la tabla
                # para gregar ese campo.
                field = newm._meta.get_field('_up')
                statements.extend(sql_add_field(oldm, '_up', field))
            if op is not None and np is None:
                # La tabla tenia un parent y ahora ya no, el campo '_up'
                # debe desaparecer
                statements.extend(sql_drop_field(oldm, '_up_id'))
            statements.extend(sql_rename_model(oldm, newm))
            # Y finalmente, actualizamos las tablas hijas
            for old_child in children:
                new_child = copy(old_child)
                new_child.model, new_child.parent = None, cur_instance
                statements.extend(update_table(old_child, new_child, True))
    if recurring:
        return statements
    else:
        execute(statements)


def delete_field(table, field):
    """Borra un campo de una tabla"""
    try:
        execute(sql_drop_field(table.model, field._db_name()))
    except Exception:
        pass


def update_field(table, old_instance, current_instance):
    """Actualiza o modifica un campo de una tabla de la base de datos"""
    old, new = old_instance, current_instance
    idxname = "idx%d" % new.pk
    model, name = table.model, new._db_name()
    if not old:
        if new.null:
            statements = sql_add_field(model, name, new.field)
        else:
            # La base de datos se puede quejar de que agreguemos un campo not null
            # sin especificar default en una tabla existente.
            # Por eso, creamos el campo como NULL y luego lo modificamos.
            fakeold = copy(new) # no usar "old", porque si no
            fakeold.null = True # no se crean los indices
            fakename, fakefield = fakeold._db_name(), fakeold.field
            statements = sql_add_field(model, fakename, fakefield)
            field, default = new.field, new.default
            statements.extend(sql_update_null(model, name, field, default))
            statements.extend(sql_modify_field(model, name, field))
    else:
        old_name, field = old._db_name(), new.field
        statements = list()
        # si cambia la tabla, mal rollo -> lanzamos ValueError
        if old.table != new.table:
            raise ValueError(_('No esta permitido cambiar la tabla'))
        # si se elimina la restriccion de unico, quito el indice.
        if old.index != new.index and old.index:
            statements.extend(sql_drop_index(model, old_name, idxname))
        # si cambia el nombre, rename previo
        if old_name != name:
            statements.extend(sql_rename_field(model, old_name, name, field))
        # si cambia el valor de null, nos aseguramos de que no hay valores null
        if old.null and not new.null:
            statements.extend(sql_update_null(model, name, field, new.default))
        statements.extend(sql_modify_field(model, name, field))
    # si el campo ha adquirido un indice, lo indexo
    if not old or old.index != new.index:
        # usar un nombre de indice no ligado al nombre del campo permite
        # que no haya que cambiarlo si se renombra el mismo.
        if new.index == UNIQUE_INDEX:
           statements.extend(sql_add_unique(model, name, idxname))
        elif new.index == MULTIPLE_INDEX:
           statements.extend(sql_add_index(model, name, idxname))
    execute(statements)


def update_dynamic(field, dynamic):
    old_name = field._dynamic_name(not dynamic)
    new_name = field._dynamic_name(dynamic)
    execute(sql_rename_field(field.table.model, old_name, new_name, field.field))

