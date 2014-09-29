#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import pickle
import binascii

from ..config import config
from ..models import Challenges, Files, Addresses, Tokens

from heartbeat import Heartbeat
from ..startup import db

__all__ = ['create_token', 'delete_token', 'add_file', 'remove_file']


def create_token(sjcx_address):
    # confirm that sjcx_address is in the list of addresses
    # for now we have a white list
    address = Addresses.query.filter(Addresses.address == sjcx_address).first()
    
    if (address is None):
        raise RuntimeError('Invalid address given: address must be in whitelist.')
    
    beat = Heartbeat()
    
    token = Tokens(token = binascii.hexlify(os.urandom(16)).decode('ascii'),
                    address = address.address,
                    heartbeat = pickle.dumps(beat))
                    
    db.session.add(token)
    db.session.commit()
    
    return (token.token,beat)

def delete_token(token):
    token = Tokens.query.filter(Tokens.token == token).first()

    if (token is None):
        raise RuntimeError('Invalid token given.  Token does not exist.')
        
    db.session.delete(token)
    db.session.commit()

def add_file(*args, **kwargs):
    raise NotImplementedError


def remove_file(*args, **kwargs):
    raise NotImplementedError

