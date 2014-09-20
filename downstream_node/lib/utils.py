#!/usr/bin/env python
# -*- coding: utf-8 -*-

from heartbeat import Challenge


def query_to_list(query):
    """ Takes a model query thing nad returns a list of dicts with the data
    Example:

    ..:
        result = utils.query_to_list(MyTable.query)

    :param query: Query object
    :return: List of dicts representing a model
    """
    lst = []
    for row in query.all():
        row_dict = {}
        for col in row.__mapper__.mapped_table.columns:
            if col.name not in ['id', 'response']:
                row_dict[col.name] = getattr(row, col.name)
        lst.append(row_dict)
    return lst


def load_heartbeat(heartbeat, query):
    """ Loads a Heartbeat object with query data

    :param heartbeat: Heartbeat instance object
    :param query: query as a SQLAlchemy query result
    :return: Loaded Heartbeat
    """
    challenges = []
    for row in query:
        challenge = Challenge(row.block, row.seed)
        challenge.response = row.response
        challenges.append(challenge)
    heartbeat.challenges = challenges
    return heartbeat
