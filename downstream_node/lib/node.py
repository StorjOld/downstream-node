#!/usr/bin/env python
# -*- coding: utf-8 -*-

from downstream_node.config import config
from downstream_node.models import Challenges

from heartbeat import Heartbeat
from downstream_node.startup import db

__all__ = ['create_token', 'delete_token', 'add_file', 'remove_file',
           'gen_challenges', 'update_challenges']


def create_token(*args, **kwargs):
    raise NotImplementedError


def delete_token(*args, **kwargs):
    raise NotImplementedError


def add_file(*args, **kwargs):
    raise NotImplementedError


def remove_file(*args, **kwargs):
    raise NotImplementedError


def gen_challenges(filepath, root_seed):
    secret = getattr(config, 'HEARTBEAT_SECRET')
    hb = Heartbeat(filepath, secret=secret)
    hb.generate_challenges(1000, root_seed)
    for challenge in hb.challenges:
        chal = Challenges(
            filepath=filepath,
            root_seed=root_seed,
            block=challenge.block,
            seed=challenge.seed,
            response=challenge.response,
        )
        db.session.add(chal)
    db.session.commit()


def update_challenges(*args, **kwargs):
    raise NotImplementedError