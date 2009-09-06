#!/usr/bin/env python
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from functools import wraps

from ..models import ChangeLog, Cache, UserView, Profile


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

