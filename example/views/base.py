#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from functools import wraps

from ..models import ChangeLog, Cache, Table, UserView, TableView, View


DEFAULT_VIEW = 'Default'


class Profile(object):

    """Filtra los atributos accesibles de un objeto"""

    def __init__(self, userview):
        try:
            if userview:
                self.view = userview.view.pk
            else:
                self.view = View.objects.get(name__iexact=DEFAULT_VIEW).pk
        except View.DoesNotExist:
            self.view = None
        self.invalidate()

    def invalidate(self):
        self.version = ChangeLog.objects.current().pk
        self._identities = dict()
        self._fields = dict()
        self._summaries = dict()

    def identity(self, model, default=None):
        return self._cached(self._identities, model, self._identity)

    def summary(self, model, default=None):
        return self._cached(self._summaries, model, self._from_view, 'summary', default)

    def fields(self, model, default=None):
        return self._cached(self._fields, model, self._from_view, 'fields', default)

    def _cached(self, d, model, func, *args):
        """Obtiene el valor de un campo de la cache"""
        pk = model._DOMD.pk
        try:
            return d[pk] 
        except KeyError:
            return d.setdefault(pk, func(model, pk, *args))

    def _from_view(self, model, pk, attrib, default):
        """Obtiene un atributo del objeto TableView"""
        try:
            item = TableView.objects.get(view=self.view, table=pk)
        except (TableView.DoesNotExist):
            if default is None:
                raise KeyError(model._DOMD.fullname)
            return default
        else:
            print "FIELDS: %s" % repr(item.fields)
            print "SUMMARY: %s" % repr(item.summary)
        return getattr(item, attrib)

    def _identity(self, model, pk):
        """Busca la identidad de una tabla"""
        try:
            uniques = set(f.name for f in Table.objects.get(pk=pk).uniques)
        except Table.DoesNotExist:
            raise KeyError(model._DOMD.fullname)
        for item in self.fields(model):
            if item in uniques:
                return item
        return 'pk'


def with_profile(func):
    """Decorador para vistas de datos.

    Se asegura de que los datos accesibles a la vista sean los permitidos
    por el perfil de usuario.

    Para eso, necesita que el usuario este autenticado.
    """
    @wraps(func)
    def view(request, *arg, **kw):
        try:
            profile = request.session['profile']
        except KeyError:
            try:
                userview = request.user.get_profile()
            except UserView.DoesNotExist:
                userview = None
            profile = Profile(userview)
            request.session['profile'] = profile
        if profile.version != ChangeLog.objects.current().pk:
            Cache.invalidate()
            profile.invalidate()
        return func(request, *arg, **kw)
    return view