#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import pickle
import binascii
import maxminddb
import base58

from datetime import datetime
from Crypto.Hash import SHA256
from RandomIO import RandomIO
from sqlalchemy import and_, desc
from heartbeat import HeartbeatError

from .startup import db, app
from .models import Address, Token, File, Contract, Chunk
from .exc import InvalidParameterError

__all__ = ['create_token',
           'delete_token',
           'get_chunk_contract',
           'lookup_contract',
           'add_file',
           'remove_file',
           'verify_proof',
           'update_contract']


def get_ip_location(remote_addr):
    """Gets the location of the request.remote_addr

    :returns: the location
    """
    # this code may need to be rethought for scalability, but for now,
    # we're going with just opening a reader each time we get a location

    location = {'country': None,
                'state': None,
                'city': None,
                'zip': None,
                'lat': None,
                'lon': None}

    reader = maxminddb.Reader(app.config['MMDB_PATH'])
    mmloc = reader.get(remote_addr)
    if (mmloc is not None):
        if ('country' in mmloc):
            location['country'] = mmloc['country']['names']['en']
        if ('subdivisions' in mmloc):
            location['state'] = mmloc['subdivisions'][0]['names']['en']
        if ('city' in mmloc):
            location['city'] = mmloc['city']['names']['en']
        if ('postal' in mmloc):
            location['zip'] = mmloc['postal']['code']
        if ('location' in mmloc):
            location['lat'] = mmloc['location']['latitude']
            location['lon'] = mmloc['location']['longitude']
    reader.close()

    return location


def assert_ip_allowed_one_more_token(remote_addr):
    """This function enforces the max token per IP count rule for
    existing tokens.
    """
    conflicting_tokens = Token.query.filter(
        Token.ip_address == remote_addr).count()

    if (app.config['MAX_TOKENS_PER_IP'] is not None and
            conflicting_tokens >= app.config['MAX_TOKENS_PER_IP']):
        # too many other tokens are using this ip address already
        # we will disallow it.
        raise InvalidParameterError(
            'IP Disallowed, only {0} tokens are permitted per IP address'.
            format(app.config['MAX_TOKENS_PER_IP']))


def process_token_ip_address(db_token, remote_addr, change=False):
    """This function enforces the max token per IP count rule for
    existing tokens.

    Checks if the given token is running with remote_addr, and if it
    isn't, it checks to make sure that the ip address is allowed an
    additional token.  if it is, then if change==True, switches token
    over to remote_addr.
    :param db_token: the database token object
    :param remote_addr: the ip address
    :param change: whether to change the token's ip address in the event
        that it is valid
    """
    if (db_token.ip_address != remote_addr):
        # possible ip address change.  check the ip address is allowed
        # to obtain another token
        assert_ip_allowed_one_more_token(remote_addr)

        # we should be good to go with the new ip
        if (change):
            location = get_ip_location(remote_addr)
            db_token.location = location
            db_token.ip_address = remote_addr


def contract_insert_next_challenge(db_contract):
    """This inserts the next challenge for the contract into the contract.

    :param db_contract: database contract object
    """
    beat = app.heartbeat

    state = db_contract.state

    try:
        chal = beat.gen_challenge(state)
    except HeartbeatError as ex:
        print(ex)
        return False

    db_contract.challenge = chal
    db_contract.due = db_contract.expiration
    db_contract.state = state
    db_contract.answered = False

    return True


def create_token(sjcx_address, remote_addr, message=None, signature=None):
    """Creates a token for the given address. Address must be in the white
    list of addresses.

    :param sjcx_address: address to use for token creation.
    :param remote_addr: ip address of the farmer requesting a token
    :returns: the token database object
    """

    # make sure that the currnet ip has not excceeded it's token count
    assert_ip_allowed_one_more_token(remote_addr)

    # make sure the address is valid
    try:
        base58.b58decode_check(sjcx_address)
    except:
        raise InvalidParameterError(
            'Invalid address given: address is not a valid SJCX address.')

    # confirm that sjcx_address is in the list of addresses
    # and meets balance requirements
    # for now we have a white list
    db_address = Address.query.filter(
        and_(Address.address == sjcx_address,
             Address.crowdsale_balance >= app.config['MIN_SJCX_BALANCE'])).\
        first()

    if (db_address is None):
        raise InvalidParameterError(
            'Invalid address given: address must be in whitelist.')

    location = get_ip_location(remote_addr)

    token = os.urandom(16)
    token_string = binascii.hexlify(token).decode('ascii')
    token_hash = SHA256.new(token).hexdigest()[:20]

    db_token = Token(token=token_string,
                     address=db_address,
                     ip_address=remote_addr,
                     farmer_id=token_hash,
                     location=location,
                     message=message,
                     signature=signature)

    db.session.add(db_token)
    db.session.commit()

    return db_token


def delete_token(token):
    """Deletes the given token.

    :param token: token to delete
    """

    db_token = Token.query.filter(Token.token == token).first()

    if (db_token is None):
        raise InvalidParameterError('Nonexistent token.')

    db.session.delete(db_token)
    db.session.commit()


def generate_test_file(size):
    """This generates a test file and prepares it
    :param size: the file size to generate and prepare
    :returns: the test file database object
    """

    seed = binascii.hexlify(os.urandom(16)).decode()

    db_file = add_file(seed, size, 1)

    db_chunk = prepare_contract(db_file)

    return db_chunk


def prepare_contract(db_file):
    """This prepares a file for issuing to farmers.  For now, considers the
    file to be a chunk, tags it and places the information in the database
    """
    beat = app.heartbeat

    chunk_stream = RandomIO(db_file.seed, db_file.size)

    (tag, state) = beat.encode(chunk_stream)

    bin_tag = pickle.dumps(tag, pickle.HIGHEST_PROTOCOL)

    tag_hash = SHA256.new(bin_tag).hexdigest()

    tag_path = os.path.join(app.config['TAGS_PATH'], tag_hash)

    # and write the tag to our temporary files
    # we will eventually need to move to a streamed tag writing if tags
    # get large but for now, we'll stick with this since we're going to use
    # merkle with short contract lifetimes
    with open(tag_path, 'wb') as f:
        f.write(bin_tag)

    db_chunk = Chunk(file=db_file,
                     state=state,
                     tag_path=tag_path)

    db.session.add(db_chunk)
    db.session.commit()

    return db_chunk


def get_chunk_contract(token, size, remote_addr):
    """In the final version, this function should analyze currently available
    file chunks and disburse contracts for files that need higher redundancy
    counts.
    In this prototype, this function should generate a random file with a seed.
    The seed can then be passed to a prototype farmer who can generate the file
    for themselves.  The contract will include the next heartbeat challenge,
    and the current heartbeat state for the encoded file.

    :param token: the token to associate this contract with
    :param size: the requested chunk size
    :param remote_addr: the ip address of the farmer requesting a chunk
    :returns: the chunk database object
    """
    # first, we need to find all the files that are not meeting their
    # redundancy requirements once we have found a candidate list, we sort
    # by when the file was added so that the most recently added file is
    # given out in a contract

    # verify the token
    db_token = Token.query.filter(Token.token == token).first()

    if (db_token is None):
        raise InvalidParameterError('Nonexistent token.')

    process_token_ip_address(db_token, remote_addr, True)

    # these are the files we are tracking with their current redundancy counts
    # for now comment this since we're just generating a file for each contract
    # candidates = db.session.query(File,func.count(Contracts.file_hash)).\
    # outerjoin(Contracts).group_by(File.hash).all()

    # if (len(candidates) == 0):
    # return None

    # sort by add date and current redundancy
    # candidates.sort(key = lambda x: x[0].added)
    # candidates.sort(key = lambda x: x[1])

    # pick the best candidate
    # file = candidates[0]

    # now we pull from pregenerated chunks
    # we need a chunk that is smaller than the requested size
    db_chunk = Chunk.query.filter(File.size <= size).join(
        File).order_by(desc(File.size)).first()

    if (db_chunk is None):
        return None

    db_contract = Contract(token=db_token,
                           file=db_chunk.file,
                           state=db_chunk.state,
                           tag_path=db_chunk.tag_path,
                           # due time and answered and challenge will be
                           # inserted when we call update_contract() below
                           start=datetime.utcnow(),
                           due=datetime.utcnow(),
                           answered=True)

    db.session.add(db_contract)

    if (not contract_insert_next_challenge(db_contract)):
        # we were not able to insert the next challenge
        # this is an issue at this stage, since the heartbeat should
        # just have been generated
        # raise an internal server error
        raise RuntimeError('Unable to initialize challenge for contract.')

    # remove the chunk from the database since it has now been used.
    db.session.delete(db_chunk)

    db.session.commit()

    return db_contract


# def add_file(chunk_path, redundancy=3, interval=60):
def add_file(seed, size, redundancy=3, interval=60):
    """This function adds a file to the database to be tracked by the
    application.

    :param seed: for prototyping, the seed of the file
    :param size: for prototyping, the size of the file
    :param chunk_path: the path to the file to track
    :param redundancy: the desired redundancy of the file
    :param interval: the desired heartbeat check interval
    :returns: the file database object
    """
    # we don't want to generate the whole file
    chunk_stream = RandomIO(seed, size)

    # first, hash the chunk to determine it's name
    h = SHA256.new()
    bufsz = 65535

    for c in iter(lambda: chunk_stream.read(bufsz), b''):
        h.update(c)

    hash = h.hexdigest()

    db_file = File(hash=hash,
                   # no path since we're prototpying
                   # path=chunk_path
                   redundancy=redundancy,
                   interval=interval,
                   added=datetime.utcnow(),
                   seed=seed,
                   size=size)

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
        raise InvalidParameterError(
            'File does not exist.  Cannot remove non existant file')

    db.session.delete(db_file)
    db.session.commit()


def lookup_contract(token, file_hash):
    """This function looks up a contract by token and file hash and returns
    the database object of that contract.

    :param token: the token string associated with this contract
    :param file_hash: the file hash associated with this contract
    :returns: the contract database object
    """
    db_token = Token.query.filter(Token.token == token).first()

    if (db_token is None):
        raise InvalidParameterError('Nonexistent token.')

    db_file = File.query.filter(File.hash == file_hash).first()

    if (db_file is None):
        raise InvalidParameterError('Invalid file hash')

    db_contract = Contract.query.filter(Contract.token_id == db_token.id,
                                        Contract.file_id == db_file.id).first()

    if (db_contract is None):
        raise InvalidParameterError('Contract does not exist.')

    return db_contract


def update_contract(token, file_hash):
    """This function updates the contract associated with the token
    and file_hash.

    :param token: the token associated with this contract
    :param file_hash: the file hash associated with this contract
    :returns: the contract after it has been updated.
    """
    db_contract = lookup_contract(token, file_hash)

    if (datetime.utcnow() >= db_contract.expiration):
        raise InvalidParameterError('Contract has expired.')

    # if the current challenge is good,
    # and has a valid challenge, use it
    if (db_contract.challenge is not None
            and datetime.utcnow() < db_contract.due):
        return db_contract

    if (not contract_insert_next_challenge(db_contract)):
        # no more challenges.
        return None

    db.session.commit()

    return db_contract


def verify_proof(token, file_hash, proof, remote_addr):
    """This queries the DB to retrieve the heartbeat, state and challenge for
    the contract id, and then checks the given proof.  Returns true if the
    proof is valid.  Can also return false if the contract is expired or if
    an ip address change has been rejected

    :param token: the token for the farmer that this proof corresponds to
    :param file_hash: the file hash for this proof
    :param proof: a heartbeat proof object that has been returned by the farmer
    :param remote_addr: the remote address that is verifying this proof
    :returns: boolean true if the proof is valid, false otherwise
    """
    db_contract = lookup_contract(token, file_hash)

    if (datetime.utcnow() >= db_contract.expiration):
        raise InvalidParameterError('Answer failed: contract expired.')

    process_token_ip_address(db_contract.token, remote_addr)

    beat = app.heartbeat
    state = db_contract.state
    chal = db_contract.challenge

    if (not db_contract.answered):
        valid = beat.verify(proof, chal, state)
    else:
        valid = db_contract.answered

    if (valid and not db_contract.answered):
        db_contract.token.hbcount += 1
        db_contract.answered = True
        # update state
        db_contract.state = state
        db.session.commit()

    return valid
