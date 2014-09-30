#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import pickle
import binascii
from datetime import datetime

from Crypto.Hash import SHA256

from ..models import Addresses, Tokens, Files

from heartbeat import Heartbeat
from ..startup import db

__all__ = ['create_token', 'delete_token', 'add_file', 'remove_file']


def create_token(sjcx_address):
    # confirm that sjcx_address is in the list of addresses
    # for now we have a white list
    address = Addresses.query.filter(Addresses.address == sjcx_address).first()

    if (address is None):
        raise RuntimeError(
            'Invalid address given: address must be in whitelist.')

    beat = Heartbeat()

    db_token = Tokens(token=binascii.hexlify(os.urandom(16)).decode('ascii'),
                   address=address.address,
                   heartbeat=pickle.dumps(beat))

    db.session.add(db_token)
    db.session.commit()

    return db_token.token

def get_heartbeat(token):
    db_token = Tokens.query.filter(Tokens.token == token).first()
    
    if (db_token is None):
        raise RuntimeError('Invalid token given.')
    
    return pickle.loads(db_token.heartbeat)

def get_chunk_contract(token):
    # first, we need to find all the files that are not meeting their
    # redundancy requirements once we have found a candidate list, we sort
    # by when the file was added so that the most recently added file is
    # given out in a contract
    
    # verify the token
    db_token = Tokens.query.filter(Tokens.token == token).first()
    
    if (db_token is None):
        raise RuntimeError('Invalid token given.')
    
    # these are the files we are tracking with their current redundancy counts
    candidates = db.session.query(Files,func.count(Contracts.file)).\
        outerjoin(Contracts).group_by(Files.hash).all()
    
    if (len(candidates) == 0):
        return None
    
    # sort by add date and current redundancy
    candidates.sort(key = lambda x: x[0].added)
    candidates.sort(key = lambda x: x[1])
    
    file = db.session.query(Files).filter(Files.hash==candidates[0].file).first()
    
    if (file is None):
        raise RuntimeError('Invalid operation. This should never happen.')
    
    beat = pickle.loads(db_token.heartbeat)
    
    with open(file.path,'rb') as f:
        (tag,state) = beat.encode(f)
        
    chal = beat.gen_challenge(state)
    
    contract = Contracts(token = token,
                         file = file.hash,
                         state = pickle.dumps(state),
                         challenge = pickle.dumps(chal),
                         expiration = datetime.utcnow() + timedelta(seconds = db_file.interval))
                         
    db.session.add(contract)
    db.session.commit()
    
    return contract.id

def delete_token(token):
    db_token = Tokens.query.filter(Tokens.token == token).first()

    if (db_token is None):
        raise RuntimeError('Invalid token given. Token does not exist.')

    db.session.delete(db_token)
    db.session.commit()


def add_file(chunk_path, redundancy=3, interval=60):
    # first, hash the chunk to determine it's name
    h = SHA256.new()
    bufsz = 65535

    with open(chunk_path,'rb') as f:
        for c in iter(lambda: f.read(bufsz), b''):
            h.update(c)

    hash = h.hexdigest()

    file = Files(hash=hash,
                 path=chunk_path,
                 redundancy=redundancy,
                 interval=interval,
                 added=datetime.utcnow())

    db.session.add(file)
    db.session.commit()

    return hash

def remove_file(hash):
    # remove all the contracts with this file
    contracts = Contracts.query(Contracts.file==hash).all()

    if (contracts is not None):
        db.session.delete(contracts)
        db.session.commit()

    # and then remove the file from the list of files
    file = Files.query(Files.hash==hash).first()

    if (file is None):
        raise RuntimeError(
            'File does not exist.  Cannot remove non existant file')

    db.session.delete(file)
    db.session.commit()

