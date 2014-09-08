#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json


def model_to_json(model):
    """ Returns a JSON representation of an SQLAlchemy-backed object.
    From Zato: https://github.com/zatosource/zato
    """
    _json = {}
    _json['fields'] = {}
    _json['pk'] = getattr(model, 'id')

    for col in model._sa_class_manager.mapper.mapped_table.columns:
        _json['fields'][col.name] = getattr(model, col.name)

    return json.dumps([_json])


def query_to_list(query):
    lst = []
    for row in query.all():
        row_dict = {}
        for col in row.__mapper__.mapped_table.columns:
            if col.name != 'id':
                row_dict[col.name] = getattr(row, col.name)
        lst.append(row_dict)
    return lst