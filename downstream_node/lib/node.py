#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import pickle
import binascii
import json
from datetime import datetime, timedelta

from Crypto.Hash import SHA256

from ..models import Address, Token, File, Contract

from heartbeat import Heartbeat
from RandomIO import RandomIO
from ..startup import db, app

__all__ = ['create_token', 'delete_token', 'get_chunk_contract', 'add_file', 'remove_file']


def create_token(sjcx_address):
    # confirm that sjcx_address is in the list of addresses
    # for now we have a white list
    address = Address.query.filter(Address.address == sjcx_address).first()

    if (address is None):
        # just put it in the db for testing
        address = Address(address=sjcx_address)
        db.session.add(address)
        db.session.commit()
        #raise RuntimeError(
        #    'Invalid address given: address must be in whitelist.')

    beat = Heartbeat()

    token = Token(token=binascii.hexlify(os.urandom(16)).decode('ascii'),
                  address=address.address,
                  heartbeat=pickle.dumps(beat))

    db.session.add(token)
    db.session.commit()

    return token


def delete_token(token):
    db_token = Token.query.filter(Token.token == token).first()

    if (db_token is None):
        raise RuntimeError('Invalid token given. Token does not exist.')

    db.session.delete(db_token)
    db.session.commit()

def get_chunk_contract(token):
    # first, we need to find all the files that are not meeting their
    # redundancy requirements once we have found a candidate list, we sort
    # by when the file was added so that the most recently added file is
    # given out in a contract
    
    # verify the token
    db_token = Token.query.filter(Token.token == token).first()
    
    if (db_token is None):
        raise RuntimeError('Invalid token given.')
    
    # these are the files we are tracking with their current redundancy counts
    # for now comment this since we're just generating a file for each contract
    # candidates = db.session.query(File,func.count(Contracts.file_hash)).\
        # outerjoin(Contracts).group_by(File.hash).all()
    
    # if (len(candidates) == 0):
        # return None
    
    # # sort by add date and current redundancy
    # candidates.sort(key = lambda x: x[0].added)
    # candidates.sort(key = lambda x: x[1])
    
    # # pick the best candidate
    # file = candidates[0]
    
    # for prototyping, we generate a file for each contract.
    seed = binascii.hexlify(os.urandom(16))
    
    file = add_file(RandomIO(seed).genfile(100,app.config['FILES_PATH']),1)
    
    beat = pickle.loads(db_token.heartbeat)
    
    with open(file.path,'rb') as f:
        (tag,state) = beat.encode(f)
        
    chal = beat.gen_challenge(state)
    
    contract = Contract(token = token,
                        file_hash = file.hash,
                        state = pickle.dumps(state),
                        challenge = pickle.dumps(chal),
                        expiration = datetime.utcnow() + timedelta(seconds = file.interval),
                        # for prototyping, include seed
                        seed = seed)

    db.session.add(contract)
    db.session.commit()
    
    # and write the tag to our temporary files
    path = os.path.join(app.config['TAGS_PATH'],file.hash)
    with open(path,'wb') as f:
        f.write(pickle.dumps(tag))
    
    return contract


def add_file(chunk_path, redundancy=3, interval=60):
    # first, hash the chunk to determine it's name
    h = SHA256.new()
    bufsz = 65535

    with open(chunk_path,'rb') as f:
        for c in iter(lambda: f.read(bufsz), b''):
            h.update(c)

    hash = h.hexdigest()

    file = File(hash=hash,
                path=chunk_path,
                redundancy=redundancy,
                interval=interval,
                added=datetime.utcnow())

    db.session.add(file)
    db.session.commit()

    return file


def remove_file(hash):
    # remove the file... contracts should also be deleted by cascading
    file = File.query.filter(File.hash==hash).first()

    if (file is None):
        raise RuntimeError(
            'File does not exist.  Cannot remove non existant file')

    db.session.delete(file)
    db.session.commit()

