#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json


def to_json(model):
    """ Returns a JSON representation of an SQLAlchemy-backed object.

    From Zato: https://github.com/zatosource/zato
    """

    _json = {}
    _json['fields'] = {}
    _json['pk'] = getattr(model, 'id')

    for col in model._sa_class_manager.mapper.mapped_table.columns:
        _json['fields'][col.name] = getattr(model, col.name)

    return json.dumps([_json])

