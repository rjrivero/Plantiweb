#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent

"""Funciones de acceso de bajo nivel a la base de datos

Funciones que proporcionan los medios necesarios para modificar en tiempo
real la base de datos, agregando, alterando y borrando tablas y campos.
"""

from copy import copy

from django.db import models, connection
from django.core.management import sql, color

from .dblog import ChangeLog
from .dbcache import MetaData, Cache


# Posibles tipos de indice
NO_INDEX       = 0
UNIQUE_INDEX   = 1
MULTIPLE_INDEX = 2


def sql_add_model(model, known=None):
    """Genera el codigo SQL necesario para crear la tabla de un modelo"""
    style, c = color.no_style(), connection.creation
    sql, deps = c.sql_create_model(model, style, known)
    return sql


def sql_add_foreign_key(model, pk, parent_model):
    """Genera el codigo SQL para las FK de un modelo"""
    tname, pname = model._meta.db_table, parent_model._meta.db_table
    sql = list()
    # por si acaso estamos re-parentando una tabla, actualizo a NULL
    sql.append("UPDATE %s SET _up_id=NULL" % tname)
    sql.append("ALTER TABLE %s ADD INDEX idx_up_id (_up_id)" % tname)
    sql.append("ALTER TABLE %s ADD CONSTRAINT fk_up_id_%d FOREIGN KEY idx_up_id (_up_id) REFERENCES %s (_id)" % (tname, pk, pname))
    return sql


def sql_drop_model(model):
    """Genera el codigo SQL para eliminar un modelo"""
    style, c, refs = color.no_style(), connection.creation, dict()
    return c.sql_destroy_model(model, refs, style)


def sql_drop_foreign_key(pk, model):
    """Genera el codigo SQL para eliminar las FK de un modelo"""
    tname = model._meta.db_table
    sql = ["ALTER TABLE %s DROP FOREIGN KEY fk_up_id_%d" % (tname, pk)]
    sql.append("ALTER TABLE %s DROP INDEX idx_up_id" % tname)
    return sql


def sql_inline_field(model, name, field):
    """Genera el codigo SQL necesario para definir un campo"""
    # HACKISH
    # El campo que creamos esta en la segunda linea del SQL (la primera es el
    # CREATE TABLE, la segunda la clave primaria)
    testtype = MetaData.create_model("test", {name: field}, 
                   model._meta.app_label, model.__module__, models.Model)
    return sql_add_model(testtype)[0].split("\n")[2].strip()


def sql_add_field(model, name, field):
    """Genera el codigo SQL para agregar un campo a una tabla"""
    inline = sql_inline_field(model, name, field)
    sql = ["ALTER TABLE %s ADD %s" % (model._meta.db_table, inline)]
    # Ya no gestionamos los indices con django, sino con SQL.
    #if field.index:
    #    sql.extend(sql_add_index(model, name, field))
    return sql


def sql_drop_field(model, name):
    """Genera el codigo SQL para eliminar un campo de una tabla"""
    return ["ALTER TABLE %s DROP %s" % (model._meta.db_table, name)]


def sql_rename_model(old_model, new_model):
    """Genera el codigo SQL para renombrar una tabla"""
    old, new = old_model._meta.db_table, new_model._meta.db_table
    if old != new:
        return ["ALTER TABLE %s RENAME TO %s" % (old, new)]
    return tuple()


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
    """Genera el codigo SQL para eliminar el indice de un campo"""
    table = model._meta.db_table
    return ["ALTER TABLE %s DROP INDEX %s" % (
                table, idxname)]


def sql_add_unique(model, name, idxname, combined=False):
    """Genera el codigo SQL para crear una clave unica
    Si combined = True, incluye en el indice tanto el campo indicado
    por "name", como el campo _up.
    """
    table = model._meta.db_table
    if combined:
        name = ', '.join((name, '_up_id'))
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


def delete_table(instance, pk, model):
    """Borra una tabla de la base de datos"""
    statements = list()
    if instance.parent:
        statements.extend(sql_drop_foreign_key(pk, model))
    for child in instance.table_set.all():
        child.delete()
    statements.extend(sql_drop_model(model))
    execute(statements)


def reindex_unique(instance, model, combined):
    """Elimina y vuelve a crear los indices unicos de una tabla"""
    statements = list()
    for field in instance.uniques:
        name, idxname = field._name, field._idxname
        statements.extend(sql_drop_index(model, name, idxname))
        statements.extend(sql_add_unique(model, name, idxname, combined))
    return statements


def pre_save_table(old_instance, old_model, cur_instance):
    """Actualiza o modifica una tabla de la base de datos"""
    if not old_instance:
        return
    op = old_instance.parent.pk if old_instance.parent else None 
    np = cur_instance.parent.pk if cur_instance.parent else None
    if op != np and op is not None:
        # no dejo reparentar una clase con un campo unico -> antes lo
        # convierto a multiple.
        # Debe ejecutarse antes de salvar la instancia, porque es
        # posible que la tabla se haya renombrado, y en ese caso las
        # modificaciones a la base de datos fallarian.
        for field in cur_instance.uniques:
           field.index = MULTIPLE_INDEX
           field.save()


def post_save_table(old_instance, old_model, cur_instance):
    """Actualiza o modifica una tabla de la base de datos"""
    oldm, newm, pk = old_model, Cache[cur_instance], cur_instance.pk
    statements = list()
    if not old_instance:
        known = list(Cache[x] for x in cur_instance.path)
        statements.extend(sql_add_model(newm, known))
        if cur_instance.parent:
            pmodel = Cache[cur_instance.parent]
            statements.extend(sql_add_foreign_key(newm, pk, pmodel))
    else:
        # si cambia la tabla padre hay que eliminar las foreign keys antiguas
        # y recrearlas.
        op = old_instance.parent.pk if old_instance.parent else None 
        np = cur_instance.parent.pk if cur_instance.parent else None
        if op != np:
            if op is None and np is not None:
                # La tabla que se habia creado no tenia campo _up_id porque su
                # modelo no tenia clave primaria. Tengo que modificar la tabla
                # para gregar ese campo.
                pmodel = Cache[cur_instance.parent]
                field = newm._meta.get_field('_up')
                statements.extend(sql_add_field(oldm, '_up', field))
                statements.extend(sql_rename_model(oldm, newm))
                statements.extend(sql_add_foreign_key(newm, pk, pmodel))
                # los campos unicos que hubiera, hay que extenderlos para ahora
                # hacerlos unicos en conjunto con el _up
                statements.extend(reindex_unique(cur_instance, newm, True))
            elif op is not None and np is None:
                # La tabla tenia un parent y ahora ya no, el campo '_up'
                # debe desaparecer.
                # pre_save_table ya debe haber pasado los indices
                # unicos a multiples, no me preocupo por reindexar
                statements.extend(sql_drop_foreign_key(pk, oldm))
                statements.extend(sql_drop_field(oldm, '_up_id'))
                statements.extend(sql_rename_model(oldm, newm))
            else:
                # pre_save_table ya debe haber pasado los indices
                # unicos a multiples, no me preocupo por reindexar
                statements.extend(sql_drop_foreign_key(pk, oldm))
                statements.extend(sql_rename_model(oldm, newm))
                pmodel = Cache[cur_instance.parent]
                statements.extend(sql_add_foreign_key(newm, pk, pmodel))
        else:
            statements.extend(sql_rename_model(oldm, newm))
    execute(statements)


def delete_field(table, field):
    """Borra un campo de una tabla"""
    try:
        execute(sql_drop_field(Cache[table], field._name))
    except Exception:
        pass


def update_field(table, old_instance, current_instance):
    """Actualiza o modifica un campo de una tabla de la base de datos"""
    old, new = old_instance, current_instance
    model, name = Cache[table], new._name
    if not old:
        if new.null:
            statements = sql_add_field(model, name, new.field)
        else:
            # La base de datos se puede quejar de que agreguemos un campo
            # not null sin especificar default en una tabla existente.
            # Por eso, creamos el campo como NULL y luego lo modificamos.
            fakeold = copy(new) # no usar "old", porque si no
            fakeold.null = True # no se crean los indices
            fakename, fakefield = fakeold._name, fakeold.field
            statements = sql_add_field(model, fakename, fakefield)
            field, default = new.field, new.default
            statements.extend(sql_update_null(model, name, field, default))
            statements.extend(sql_modify_field(model, name, field))
    else:
        old_name, field = old._name, new.field
        statements = list()
        # si cambia la tabla, mal rollo -> lanzamos ValueError
        if old.table != new.table:
            raise ValueError(_('No esta permitido cambiar la tabla'))
        # si se eliminan indices, los quito.
        if old.index != new.index and old.index:
            statements.extend(sql_drop_index(model, old_name, old._idxname))
        # si cambia el nombre, rename previo
        if old_name != name:
            statements.extend(sql_rename_field(model, old_name, name, field))
        # si cambia el valor de null, nos aseguramos de que no hay nulos
        if old.null and not new.null:
            statements.extend(sql_update_null(model, name, field,
                                              new.default))
        statements.extend(sql_modify_field(model, name, field))
    # si el campo ha adquirido un indice, lo indexo
    if not old or old.index != new.index:
        # usar un nombre de indice no ligado al nombre del campo permite
        # que no haya que cambiarlo si se renombra el mismo.
        idxname = new._idxname
        if new.index == UNIQUE_INDEX:
           combined = bool(table.parent)
           statements.extend(sql_add_unique(model, name, idxname, combined))
        elif new.index == MULTIPLE_INDEX:
           statements.extend(sql_add_index(model, name, idxname))
    execute(statements)


def update_dynamic(field, dynamic, save=True):
    """Actualiza el nombre de un campo.

    Si save == True, pasa del nombre normal al dinamico.
    Si save == False, pasa del nombre dinamico al normal.
    """
    if save:
        old_name, new_name = field.name, dynamic.name
    else:
        old_name, new_name = dynamic.name, field.name
    execute(sql_rename_field(Cache[field.table], old_name,
                             new_name, field.field))
