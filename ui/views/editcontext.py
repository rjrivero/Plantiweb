#!/usr/bin/env python
# -*- coding: utf-8 -*-
# -*- vim: expandtab tabstop=4 shiftwidth=4 smarttab autoindent


from gettext import gettext as _
from collections import namedtuple

from ..models import Field, Link, Table, Cache


class EditContext(dict):

    """Prepara la vista de edicion / creacion"""

    def __init__(self, request, model_pk, instance_pk=None):
        super(dict, self).__init__()
        self.request = request
        self._set_model(model_pk, instance_pk)

    def _get_model(self, model_pk):
        try:
            return Cache(int(model_pk))
        except (TypeError, KeyError):
            return

    def _get_item(self, model, instance_pk):
        if instance_pk is not None:
            try:
                return model._DOMD.objects.get(pk=instance_pk)
            except model.DoesNotExist:
                return
        return model()

    def _set_model(self, model_pk, instance_pk):
        """Crea las entradas model, form, item, valid y cleaned

        model: modelo que se corresponde con la PK proporcionada.
        form: formulario para la edicion del modelo.
        item: objeto editado o agregado, con los cambios recibidos.
        valid: True si todos los valores recibidos por POST son validos.
        data: datos recibidos.
        """
        model, form, item, valid, data = None, None, None, False, None
        model = self._get_model(model_pk)
        if model is not None:
            full_name = model._DOMD.fullname
            item = self._get_item(model, instance_pk)
            initial=dict(item.iteritems())
            if item is not None:
                form_type = self.request.session['profile'].form(model)
                if form_type is not None:
                    if self.request.POST:
                        form = form_type(self.request.POST, initial=initial)
                        valid = form.is_valid()
                        if valid:
                            data = form.cleaned_data
                        else:
                            data = form.partial_cleaned_data
                    else:
                        form = form_type(initial=initial)
                        data = dict()
                    for key, val in data.iteritems():
                        setattr(item, key, val or None)
        self.update(locals())

