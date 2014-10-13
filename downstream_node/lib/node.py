#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import pickle
import binascii
import base58
from datetime import datetime, timedelta

from Crypto.Hash import SHA256

from ..models import Address, Token, File, Contract

from RandomIO import RandomIO
from ..startup import db, app

__all__ = ['create_token',
           'delete_token',
           'get_chunk_contract',
           'lookup_contract',
           'add_file',
           'remove_file',
           'verify_proof',
           'update_contract']


def create_token(sjcx_address):
    """Creates a token for the given address. For now, addresses will not be
    enforced, and anyone can acquire a token.

    :param sjcx_address: address to use for token creation.  for now, just
    allow any address.
    :returns: the token database object
    """
    # confirm that sjcx_address is in the list of addresses
    # for now we have a white list
    db_address = Address.query.filter(Address.address == sjcx_address).first()

    if (db_address is None):
        try:
            base58.b58decode_check(sjcx_address)
        except:
            raise RuntimeError('Invalid address given.')
        # just put it in the db for testing
        db_address = Address(address=sjcx_address)
        db.session.add(db_address)
        db.session.commit()
        # raise RuntimeError(
        #    'Invalid address given: address must be in whitelist.')

    beat = app.config['HEARTBEAT']()

    db_token = Token(token=binascii.hexlify(os.urandom(16)).decode('ascii'),
                     address_id=db_address.id,
                     heartbeat=pickle.dumps(beat, pickle.HIGHEST_PROTOCOL))

    db.session.add(db_token)
    db.session.commit()

    return db_token


def delete_token(token):
    """Deletes the given token.

    :param token: token to delete
    """

    db_token = Token.query.filter(Token.token == token).first()

    if (db_token is None):
        raise RuntimeError('Invalid token given. Token does not exist.')

    db.session.delete(db_token)
    db.session.commit()


def get_chunk_contract(token):
    """In the final version, this function should analyze currently available
    file chunks and disburse contracts for files that need higher redundancy
    counts.
    In this prototype, this function should generate a random file with a seed.
    The seed can then be passed to a prototype farmer who can generate the file
    for themselves.  The contract will include the next heartbeat challenge,
    and the current heartbeat state for the encoded file.

    :param token: the token to associate this contract with
    :returns: the chunk database object
    """
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
    seed = binascii.hexlify(os.urandom(16)).decode()

    db_file = add_file(RandomIO(seed).genfile(app.config['TEST_FILE_SIZE'],
                                              app.config['FILES_PATH']), 1)

    beat = pickle.loads(db_token.heartbeat)

    with open(db_file.path, 'rb') as f:
        (tag, state) = beat.encode(f)

    db_contract = Contract(token_id=db_token.id,
                           file_id=db_file.id,
                           state=pickle.dumps(state, pickle.HIGHEST_PROTOCOL),
                           # expiration and answered will be updated and
                           # challenge will be inserted when we call 
                           # update_contract() below
                           expiration=datetime.utcnow(),
                           answered=True,
                           # for prototyping, include seed
                           seed=seed,
                           size=app.config['TEST_FILE_SIZE'])

    db.session.add(db_contract)
    db.session.commit()

    db_contract = update_contract(db_token.token, db_file.hash)

    # the tag path is tied to the contract id.  in the final application
    # there will be some management for the tags since once they have been
    # downloaded by the farmer, they should be deleted.  might require a
    # tags database table.
    tag_path = os.path.join(app.config['TAGS_PATH'], str(db_contract.id))

    db_contract.tag_path = tag_path
    db.session.commit()

    # and write the tag to our temporary files
    with open(db_contract.tag_path, 'wb') as f:
        pickle.dump(tag, f, pickle.HIGHEST_PROTOCOL)

    return db_contract


def add_file(chunk_path, redundancy=3, interval=60):
    """This function adds a file to the databse to be tracked by the
    application.

    :param chunk_path: the path to the file to track
    :param redundancy: the desired redundancy of the file
    :param interval: the desired heartbeat check interval
    :returns: the file database object
    """
    # first, hash the chunk to determine it's name
    h = SHA256.new()
    bufsz = 65535

    with open(chunk_path, 'rb') as f:
        for c in iter(lambda: f.read(bufsz), b''):
            h.update(c)

    hash = h.hexdigest()

    db_file = File(hash=hash,
                   path=chunk_path,
                   redundancy=redundancy,
                   interval=interval,
                   added=datetime.utcnow())

    db.session.add(db_file)
    db.session.commit()

    return db_file


def remove_file(hash):
    """This function removes a file from tracking in the database.  It
    will also remove any associated contracts

    :param hash: the hash of the file to remove
    """
    # remove the file... contracts should also be deleted by cascading
    db_file = File.query.filter(File.hash == hash).first()

    if (db_file is None):
        raise RuntimeError(
            'File does not exist.  Cannot remove non existant file')

    db.session.delete(db_file)
    db.session.commit()


def lookup_contract(token, file_hash):
    """This function looks up a contract by token and file hash and returns
    the database object of that contract.

    :param token: the token associated with this contract
    :param file_hash: the file hash associated with this contract
    :returns: the contract database object
    """
    db_token = Token.query.filter(Token.token == token).first()

    if (db_token is None):
        raise RuntimeError('Invalid token')

    db_file = File.query.filter(File.hash == file_hash).first()

    if (db_file is None):
        raise RuntimeError('Invalid file hash')

    db_contract = Contract.query.filter(Contract.token_id == db_token.id,
                                        Contract.file_id == db_file.id).first()

    if (db_contract is None):
        raise RuntimeError('Contract does not exist.')

    return db_contract


def contract_valid(contract):
    """This function checks whether a contract is still valid
    
    A contract is valid if:
        1) the current time is less than the expiration time OR
        2) the challenge has been answered and the current time
           is less than the expiration time plus the file interval
    """

    if (datetime.utcnow() < contract.expiration):
        return True

    final_expiration = contract.expiration \
        + timedelta(seconds=contract.file.interval)

    if (contract.answered and datetime.utcnow() < final_expiration):
        return True

    return False


def update_contract(token, file_hash):
    """This function updates the contract associated with the token 
    and file_hash.

    :param token: the token associated with this contract
    :param file_hash: the file hash associated with this contract
    :returns: the contract after it has been updated.
    """ 
    db_contract = lookup_contract(token, file_hash)

    if (not contract_valid(db_contract)):
        raise RuntimeError('Contract has expired.')
        
    # if the current challenge is good, 
    # and has a valid challenge, use it
    if (datetime.utcnow() < db_contract.expiration
        and db_contract.challenge is not None):
        return db_contract
    
    beat = pickle.loads(db_contract.token.heartbeat)

    state = pickle.loads(db_contract.state)

    chal = beat.gen_challenge(state)

    new_expiration = db_contract.expiration + timedelta(db_contract.file.interval)
    
    db_contract.challenge = pickle.dumps(chal, pickle.HIGHEST_PROTOCOL)
    db_contract.expiration = new_expiration
    db_contract.state = pickle.dumps(state, pickle.HIGHEST_PROTOCOL)
    db_contract.answered = False
    
    db.session.add(db_contract)
    db.session.commit()

    return db_contract


def verify_proof(token, file_hash, proof):
    """This queries the DB to retrieve the heartbeat, state and challenge for
    the contract id, and then checks the given proof.  Returns true if the
    proof is valid.

    :param token: the token for the farmer that this proof corresponds to
    :param file_hash: the file hash for this proof
    :param proof: a heartbeat proof object that has been returned by the farmer
    :returns: boolean true if the proof is valid, false otherwise
    """
    db_contract = lookup_contract(token, file_hash)

    if (not contract_valid(db_contract)):
        return False

    beat = pickle.loads(db_contract.token.heartbeat)
    state = pickle.loads(db_contract.state)
    chal = pickle.loads(db_contract.challenge)

    valid = beat.verify(proof, chal, state)
    
    if (valid):
        db_contract.answered = True
        db.session.commit()
    
    return valid
