#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pickle
import siggy
import ijson
import traceback

from flask import jsonify, request, Response, stream_with_context
from sqlalchemy import func, desc
from sqlalchemy.sql import select
from datetime import datetime

from .startup import app, db
from .node import (create_token, get_chunk_contracts,
                   verify_proof,  update_contract,
                   process_token_ip_address)
from .models import Token, Address, Contract, File, update_uptime_summary
from .exc import InvalidParameterError, NotFoundError, HttpHandler
from .streamencoder import JSONEncoder as StreamEncoder


@app.route('/')
def api_index():
    return jsonify(msg='ok')


@app.route('/status/list/',
           defaults={'o': False, 'd': False, 'sortby': 'id',
                     'limit': None, 'page': None})
@app.route('/status/list/<int:limit>',
           defaults={'o': False, 'd': False, 'sortby': 'id', 'page': None})
@app.route('/status/list/<int:limit>/<int:page>',
           defaults={'o': False, 'd': False, 'sortby': 'id'})
@app.route('/status/list/by/<sortby>',
           defaults={'o': False, 'd': False, 'limit': None, 'page': None})
@app.route('/status/list/by/d/<sortby>',
           defaults={'o': False, 'd': True, 'limit': None, 'page': None})
@app.route('/status/list/by/<sortby>/<int:limit>',
           defaults={'o': False, 'd': False, 'page': 0})
@app.route('/status/list/by/d/<sortby>/<int:limit>',
           defaults={'o': False, 'd': True, 'page': 0})
@app.route('/status/list/by/<sortby>/<int:limit>/<int:page>',
           defaults={'o': False, 'd': False})
@app.route('/status/list/by/d/<sortby>/<int:limit>/<int:page>',
           defaults={'o': False, 'd': True})
@app.route('/status/list/online/',
           defaults={'o': True, 'd': False, 'sortby': 'id',
                     'limit': None, 'page': None})
@app.route('/status/list/online/<int:limit>',
           defaults={'o': True, 'd': False, 'sortby': 'id', 'page': None})
@app.route('/status/list/online/<int:limit>/<int:page>',
           defaults={'o': True, 'd': False, 'sortby': 'id'})
@app.route('/status/list/online/by/<sortby>',
           defaults={'o': True, 'd': False, 'limit': None, 'page': None})
@app.route('/status/list/online/by/d/<sortby>',
           defaults={'o': True, 'd': True, 'limit': None, 'page': None})
@app.route('/status/list/online/by/<sortby>/<int:limit>',
           defaults={'o': True, 'd': False, 'page': 0})
@app.route('/status/list/online/by/d/<sortby>/<int:limit>',
           defaults={'o': True, 'd': True, 'page': 0})
@app.route('/status/list/online/by/'
           '<sortby>/<int:limit>/<int:page>',
           defaults={'o': True, 'd': False})
@app.route('/status/list/online/by/d/'
           '<sortby>/<int:limit>/<int:page>',
           defaults={'o': True, 'd': True})
def api_downstream_status_list(o, d, sortby, limit, page):
    with HttpHandler(app.mongo_logger) as handler:
        # status page rewrite
        # lets get all the data we need with one query and then do the
        # sorting as we need

        sort_map = {'id': 'id',
                    'address': 'address',
                    'uptime': 'uptime',
                    'heartbeats': 'heartbeats',
                    'contracts': 'contract_count',
                    'size': 'size',
                    'online': 'online'}

        if (sortby not in sort_map):
            raise InvalidParameterError('Invalid sort.')

        update_uptime_summary()

        farmer_stmt = select([Token.__table__.c.farmer_id.label('id'),
                              Address.__table__.c.address,
                              Token.__table__.c.location,
                              Token.__table__.c.hbcount.label('heartbeats'),
                              Token.online_count.label('contract_count'),
                              func.max(Contract.__table__.c.due)
                              .label('last_due'),
                              Token.online_size.label('size'),
                              Token.online.label('online'),
                              Token.fraction.label('uptime')])\
            .select_from(Token.__table__.join(Address.__table__)
                         .join(Contract.__table__.join(File.__table__),
                               isouter=True))\
            .group_by('id')

        # now get the tokens we need
        if (d):
            sort_stmt = desc(sort_map[sortby])
        else:
            sort_stmt = sort_map[sortby]

        farmer_stmt = farmer_stmt.order_by(sort_stmt)

        if (limit is not None):
            farmer_stmt = farmer_stmt.limit(limit)

        if (page is not None):
            farmer_stmt = farmer_stmt.offset(limit * page)

        farmer_list = db.engine.execute(farmer_stmt)

        farmers = [dict(id=a.id,
                        address=a.address,
                        location=a.location,
                        uptime=float(round(a.uptime * 100, 2)),
                        heartbeats=a.heartbeats,
                        contracts=int(a.contract_count),
                        last_due=a.last_due,
                        size=int(a.size if a.size is not None else 0),
                        online=a.online)
                   for a in farmer_list
                   if not o or a.online]

        return jsonify(farmers=farmers)

    return handler.response


@app.route('/status/show/<farmer_id>')
def api_downstream_status_show(farmer_id):
    with HttpHandler(app.mongo_logger) as handler:
        a = Token.query.filter(Token.farmer_id == farmer_id).first()

        if (a is None):
            raise NotFoundError('Nonexistant farmer id.')

        response = dict(id=a.farmer_id,
                        address=a.addr,
                        location=a.location,
                        uptime=round(a.online_time * 100, 2),
                        heartbeats=a.hbcount,
                        contracts=a.contract_count,
                        last_due=a.last_due,
                        size=a.size,
                        online=a.online)

        return jsonify(response)

    return handler.response


@app.route('/new/<sjcx_address>', methods=['GET', 'POST'])
def api_downstream_new_token(sjcx_address):
    # generate a new token
    with HttpHandler(app.mongo_logger) as handler:
        handler.context['sjcx_address'] = sjcx_address
        handler.context['remote_addr'] = request.remote_addr

        message = None
        signature = None
        if (app.config['REQUIRE_SIGNATURE']):
            if (request.method == 'POST'):
                # need to have a restriction on posted data size....
                # for now, we'll restrict message length
                d = request.get_json(silent=True)

                # put the posted data into the context for logging
                handler.context['posted_data'] = d

                if (d is False or not isinstance(d, dict)
                        or 'signature' not in d or 'message' not in d):
                    raise InvalidParameterError(
                        'Posted data must be JSON encoded object including '
                        '"signature" and "message"')

                if (len(d['message']) > app.config['MAX_SIG_MESSAGE_SIZE']):
                    raise InvalidParameterError(
                        'Please restrict your message to less than {0} bytes.'
                        .format(app.config['MAX_SIG_MESSAGE_SIZE']))

                if (len(d['signature']) != siggy.SIGNATURE_LENGTH):
                    raise InvalidParameterError(
                        'Your signature is the wrong length.  It should be {0}'
                        'bytes.'.format(siggy.SIGNATURE_LENGTH))

                message = d['message']
                signature = d['signature']

                # parse the signature and message
                if (not siggy.verify_signature(message,
                                               signature,
                                               sjcx_address)):
                    raise InvalidParameterError('Signature invalid.')
            else:
                raise InvalidParameterError(
                    'New token requests must include posted signature proving '
                    'ownership of farming address')

        db_token = create_token(
            sjcx_address, request.remote_addr, message, signature)
        beat = app.heartbeat
        pub_beat = beat.get_public()

        response = dict(token=db_token.token,
                        type=type(beat).__name__,
                        heartbeat=pub_beat.todict())

        if (app.mongo_logger is not None):
            app.mongo_logger.log_event('new', {'context': handler.context,
                                               'response': response})

        return jsonify(response)

    return handler.response


@app.route('/heartbeat/<token>')
def api_downstream_heartbeat(token):
    """This route gets the heartbeat for a token.
    The heartbeat is the object that contains data for proving
    existence of a file (for example, Swizzle, Merkle objects)
    Provided for nodes that need to recover their heartbeat.
    The heartbeat does not contain any private information,
    so having someone else's heartbeat does not help you.
    """
    with HttpHandler(app.mongo_logger) as handler:
        handler.context['token'] = token
        handler.context['remote_addr'] = request.remote_addr
        db_token = Token.query.filter(Token.token == token).first()

        if (db_token is None):
            raise NotFoundError('Nonexistent token.')

        beat = app.heartbeat
        pub_beat = beat.get_public()
        response = dict(token=db_token.token,
                        type=type(beat).__name__,
                        heartbeat=pub_beat.todict())

        if (app.mongo_logger is not None):
            app.mongo_logger.log_event('heartbeat',
                                       {'context': handler.context,
                                        'response': response})

        return jsonify(response)

    return handler.response


@app.route('/chunk/<token>',
           defaults={'size': app.config['DEFAULT_CHUNK_SIZE']})
@app.route('/chunk/<token>/<int:size>')
def api_downstream_chunk_contract(token, size):
    with HttpHandler(app.mongo_logger) as handler:
        handler.context['token'] = token
        handler.context['size'] = size
        handler.context['remote_addr'] = request.remote_addr

        # verify the token
        db_token = Token.query.filter(Token.token == token).first()

        if (db_token is None):
            raise InvalidParameterError('Nonexistent token.')

        process_token_ip_address(db_token, request.remote_addr, True)

        db_contracts = get_chunk_contracts(db_token, size)

        def get_chunks():
            for db_contract in db_contracts:
                with open(db_contract.tag_path, 'rb') as f:
                    tag = pickle.load(f)
                chal = db_contract.challenge

                db.session.flush()
                # we now delete the tag since it has been sent
                # (we never actually create the file)
                os.remove(db_contract.tag_path)

                chunk = dict(seed=db_contract.file.seed,
                             size=db_contract.file.size,
                             file_hash=db_contract.id,
                             challenge=chal.todict(),
                             tag=tag.todict(),
                             due=(db_contract.due - datetime.utcnow()).
                             total_seconds())

                yield chunk

        if (app.mongo_logger is not None):
            # we'll remove the tag becauase it could potentially be very large
            app.mongo_logger.log_event('chunk',
                                       {'context': handler.context,
                                        'response': 'REDACTED (streaming)'})

        response = dict(chunks=get_chunks())

        return Response(stream_with_context(StreamEncoder(stream=True)
                                            .iterencode(response)),
                        mimetype='application/json')

    return handler.response


def get_contract_iter(hash_iterable, key=None, bufsz=100):
    """calls next() on hash_iterable until at most bufsz hashes have
    been retrieved, at which point it queries the database and
    retrieves all the contracts associated with those hashes.
    then it yields each contract associated with the hashes in
    hash_iterable, or None if a contract was not found associated with
    the hash specified.  yields a list [contract, hash_iterable_item]
    """
    done = False
    while (not done):
        count = 0
        map = dict()
        try:
            while (count < bufsz):
                item = next(hash_iterable)
                if (key is None):
                    # item is id
                    id = int(item)
                else:
                    id = int(item[key])
                map[id] = [None, item]
                count += 1
        except StopIteration:
            done = True
        except:
            print(traceback.format_exc())
            done = True
        if (count == 0):
            return
        contracts = Contract.query.filter(Contract.id.in_(map.keys())).all()
        for c in contracts:
            map[c.id][0] = c
        for pair in map.values():
            yield pair


def get_challenges(pair_iterator, token_id):
    for (db_contract, item) in pair_iterator:
        if (db_contract is None
                or db_contract.token_id != token_id):
            challenge = dict(
                file_hash=item, error='contract not found')
            yield challenge
            continue

        challenge = dict(file_hash=db_contract.id)

        try:
            db_contract = update_contract(db_contract)
        except InvalidParameterError:
            challenge['error'] = 'contract expired'
            yield challenge
            continue

        if (db_contract is None):
            challenge['status'] = 'no more challenges'
            yield challenge
            continue

        challenge['challenge'] = db_contract.challenge.todict()
        challenge['due'] = (db_contract.due - datetime.utcnow())\
            .total_seconds()
        challenge['answered'] = db_contract.answered

        yield challenge

    db.session.commit()


@app.route('/challenge/<token>', methods=['GET', 'POST'])
def api_downstream_chunk_contract_status(token):
    """For prototyping, this will generate a new challenge,
    returns limit online contracts.  any expired contracts will not
    be sent

    :param limit: only update limit contracts.
    :param answered: only update answered contracts
    """
    with HttpHandler(app.mongo_logger) as handler:
        handler.context['token'] = token
        handler.context['remote_addr'] = request.remote_addr

        db_token = Token.query.filter(Token.token == token).first()

        if (db_token is None):
            raise InvalidParameterError('Nonexistent token.')

        if (request.method == 'POST'):
            # try to stream POST data
            hash_iterable = ijson.items(request.stream, 'hashes.item')

            pair_iterator = get_contract_iter(hash_iterable)
        else:
            def get_all():
                contracts = Contract.query.filter(
                    Contract.token_id == db_token.id).all()
                for c in contracts:
                    yield (c, c.id)

            pair_iterator = get_all()

        if (app.mongo_logger is not None):
            app.mongo_logger.log_event('challenge',
                                       {'context': handler.context,
                                        'response': 'REDACTED (streaming)'})

        response = dict(
            challenges=get_challenges(pair_iterator, db_token.id))

        return Response(stream_with_context(StreamEncoder(stream=True)
                                            .iterencode(response)),
                        mimetype='application/json')

    return handler.response


def get_verification_reports(pair_iterator, beat, token_id):
    for (db_contract, item) in pair_iterator:
        if (db_contract is None
                or db_contract.token_id != token_id):
            r = dict(file_hash=item['file_hash'],
                     error='contract not found')
            yield r
            continue

        r = dict(file_hash=db_contract.id)

        try:
            proof = beat.proof_type().fromdict(
                item['proof'])
        except:
            r['error'] = 'Proof corrupted'
            yield r
            continue

        try:
            if (not verify_proof(db_contract,
                                 proof,
                                 datetime.utcnow())):
                r['error'] = 'Invalid proof'
                yield r
                continue
        except InvalidParameterError as ex:
            r['error'] = str(ex)
            yield r
            continue

        r['status'] = 'ok'
        yield r

    db.session.commit()


@app.route('/answer/<token>', methods=['POST'])
def api_downstream_challenge_answer(token):
    with HttpHandler(app.mongo_logger) as handler:
        handler.context['token'] = token
        handler.context['remote_addr'] = request.remote_addr

        db_token = Token.query.filter(Token.token == token).first()

        if (db_token is None):
            raise InvalidParameterError('Nonexistent token.')

        process_token_ip_address(db_token, request.remote_addr)

        beat = app.heartbeat

        hash_iterable = ijson.items(request.stream, 'proofs.item')

        pair_iterator = get_contract_iter(
            hash_iterable, key='file_hash')

        if (app.mongo_logger is not None):
            app.mongo_logger.log_event('answer',
                                       {'context': handler.context,
                                        'response': 'REDACTED (streaming)'})

        response = dict(
            report=get_verification_reports(pair_iterator, beat, db_token.id))

        return Response(stream_with_context(StreamEncoder(stream=True)
                                            .iterencode(response)),
                        mimetype='application/json')

    return handler.response
