#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from django.db import models, connection
from django.core.management import sql, color

from .dblog import ChangeLog


def create_model(name, app_label, module, attrs=None):
    """Crea un modelo dinamicamente"""
    class Meta:
        pass
    setattr(Meta, 'app_label', app_label)
    setattr(Meta, 'db_table', '%s_%s' % (app_label, name))
    attrs = attrs or dict()
    attrs.update({'Meta': Meta, '__module__': module})
    # El typename cambia cada vez que recargamos el modelo, porque
    # si no, el mecanismo de cache de Django hace que no se refresquen
    # los cambios.
    typename = "%s%d" % (str(name), ChangeLog.objects.current().pk)
    return type(typename, (models.Model,), attrs)


def sql_model(model, known=None):
    """Genera el codigo SQL necesario para crear la tabla de un modelo"""
    style = color.no_style()
    sql, deps = connection.creation.sql_create_model(model, style, known)
    print "sql recibido: %s" % str(sql)
    print "dummy recibido: %s" % str(deps)
    print ("fk: %s" % str(connection.creation.sql_indexes_for_model(model, style)))
    return sql[0]


def sql_field(model, name, field):
    """Genera el codigo SQL necesario para crear un campo de una tabla"""
    # El typename cambia cada vez que recargamos el modelo, porque
    # si no, el mecanismo de cache de Django hace que no se refresquen
    # los cambios.
    typename = "test%d" % ChangeLog.objects.current().pk
    model = create_model(typename, model._meta.app_label, model.__module__,
                {str(name): field})
    return sql_model(model).split("\n")[2].strip()


def delete_table(model):
    """Borra una tabla de la base de datos"""
    sql = ChangeLog().log("DROP TABLE %s" % str(model._meta.db_table))
    connection.cursor().execute(sql)


def update_table(old_instance, old_model, current_instance):
    """Actualiza o modifica una tabla de la base de datos"""
    if not old_instance:
        sql = ChangeLog().log(current_instance.sql())
        connection.cursor().execute(sql)
    elif old_instance.name != current_instance.name:
        sql = ChangeLog().log("ALTER TABLE %s RENAME TO %s" %
                  (old_model._meta.db_table,
                   current_instance.model._meta.db_table))
        connection.cursor().execute(sql)


def delete_field(table, field):
    """Borra un campo de una tabla"""
    try:
        sql = ChangeLog().log("ALTER TABLE %s DROP COLUMN %s" % (
              str(table.model._meta.db_table), str(field.name)))
        connection.cursor().execute(sql)
    except Exception:
        pass


def update_field(table, old_instance, current_instance):
    """Actualiza o modifica un campo de una tabla de la base de datos"""
    tnm = table.model._meta.db_table
    sql = sql_field(table.model,
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
        cursor.execute(ChangeLog().log(sql))

