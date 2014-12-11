#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pickle
import siggy

from flask import jsonify, request
from sqlalchemy import func, desc, bindparam, text, Float
from sqlalchemy.sql import select
from sqlalchemy.sql.expression import false
from datetime import datetime

from .startup import app, db
from .node import (create_token, get_chunk_contract,
                   verify_proof,  update_contract,
                   lookup_contract)
from .models import Token, Address, Contract, File
from .exc import InvalidParameterError, NotFoundError, HttpHandler
from .uptime import UptimeSummary, UptimeCalculator


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

        tokens = Token.__table__
        addresses = Address.__table__
        files = File.__table__
        contracts = Contract.__table__

        expiration = func.IF(contracts.c.answered,
                             func.TIMESTAMPADD(text('second'),
                                               files.c.interval,
                                               contracts.c.due),
                             contracts.c.due)

        total_time = func.TIMESTAMPDIFF(text('second'),
                                        tokens.c.start,
                                        tokens.c.end)

        fraction = func.IF(func.ABS(total_time) > 0,
                           func.cast(func.TIMESTAMPDIFF(
                               text('second'),
                               '1970-01-01',
                               tokens.c.upsum), Float) /
                           func.cast(total_time, Float),
                           0)

        conn = db.engine.connect()

        cache_stmt = select([tokens.c.id,
                             tokens.c.start,
                             tokens.c.end,
                             tokens.c.upsum])

        cache_info = conn.execute(cache_stmt).fetchall()

        uncached_stmt = select([contracts.c.id,
                                expiration.label('expiration'),
                                contracts.c.start,
                                contracts.c.cached]).\
            where(contracts.c.cached == false())

        new_cache = list()
        new_summary = list()

        # calculate uptime for each farmer
        for token in cache_info:
            # get info on contracts associated with this token
            s = uncached_stmt.where(contracts.c.token_id == token.id)

            uncached = conn.execute(s).fetchall()

            if (len(uncached) == 0):
                continue

            if (token.start is None):
                start = min([x.start for x in uncached])
            else:
                start = token.start

            calc = UptimeCalculator(
                uncached, UptimeSummary(start, token.end, token.upsum))

            summary = calc.update()

            # update whether contracts have been cached or not
            for c in calc.updated:
                new_cache.append({'contract_id': c})

            # and update the summary
            new_summary.append({'token_id': token.id,
                                'start': summary.start,
                                'end': summary.end,
                                'upsum': summary.uptime})

        if (len(new_cache) > 0):
            s = contracts.update().where(contracts.c.id == bindparam('contract_id')).\
                values(cached=True)

            conn.execute(s, new_cache)

        if (len(new_summary) > 0):
            s = tokens.update().where(tokens.c.id == bindparam('token_id')).\
                values(start=bindparam('start'),
                       end=bindparam('end'),
                       upsum=bindparam('upsum'))

            conn.execute(s, new_summary)

        farmer_stmt = select([tokens.c.farmer_id.label('id'),
                              addresses.c.address,
                              tokens.c.location,
                              tokens.c.hbcount.label('heartbeats'),
                              func.count(contracts.c.id).
                              label('contract_count'),
                              func.max(contracts.c.due).label('last_due'),
                              func.sum(contracts.c.size).label('size'),
                              (func.max(expiration) > datetime.utcnow())
                              .label('online'),
                              fraction.label('uptime')]).\
            select_from(tokens.join(contracts).join(addresses).join(files))

        farmer_stmt = farmer_stmt.group_by('id')

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

        farmer_list = conn.execute(farmer_stmt)

        farmers = [dict(id=a.id,
                        address=a.address,
                        location=a.location,
                        uptime=float(round(a.uptime * 100, 2)),
                        heartbeats=a.heartbeats,
                        contracts=a.contract_count,
                        last_due=a.last_due,
                        size=int(a.size),
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
                        uptime=round(a.uptime * 100, 2),
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
        beat = db_token.heartbeat
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

        beat = db_token.heartbeat
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

        db_contract = get_chunk_contract(token, size, request.remote_addr)

        with open(db_contract.tag_path, 'rb') as f:
            tag = pickle.load(f)
        chal = db_contract.challenge

        # now since we are prototyping, we can delete the tag and file
        os.remove(db_contract.file.path)
        os.remove(db_contract.tag_path)

        response = dict(seed=db_contract.seed,
                        size=db_contract.size,
                        file_hash=db_contract.file.hash,
                        challenge=chal.todict(),
                        tag=tag.todict(),
                        due=(db_contract.due - datetime.utcnow()).
                        total_seconds())

        if (app.mongo_logger is not None):
            # we'll remove the tag becauase it could potentially be very large
            rsummary = {key: response[key] for key in ['seed',
                                                       'size',
                                                       'file_hash',
                                                       'due',
                                                       'challenge']}
            rsummary['tag'] = 'REDACTED'
            app.mongo_logger.log_event('chunk',
                                       {'context': handler.context,
                                        'response': rsummary})

        return jsonify(response)

    return handler.response


@app.route('/challenge/<token>/<file_hash>')
def api_downstream_chunk_contract_status(token, file_hash):
    """For prototyping, this will generate a new challenge
    """
    with HttpHandler(app.mongo_logger) as handler:
        handler.context['token'] = token
        handler.context['file_hash'] = file_hash
        handler.context['remote_addr'] = request.remote_addr
        db_contract = update_contract(token, file_hash)

        response = dict(challenge=db_contract.challenge.todict(),
                        due=(db_contract.due - datetime.utcnow()).
                        total_seconds(),
                        answered=db_contract.answered)

        if (app.mongo_logger is not None):
            app.mongo_logger.log_event('challenge',
                                       {'context': handler.context,
                                        'response': response})

        return jsonify(response)

    return handler.response


@app.route('/answer/<token>/<file_hash>', methods=['POST'])
def api_downstream_challenge_answer(token, file_hash):
    with HttpHandler(app.mongo_logger) as handler:
        handler.context['token'] = token
        handler.context['file_hash'] = file_hash
        handler.context['remote_addr'] = request.remote_addr
        d = request.get_json(silent=True)

        if (d is False or not isinstance(d, dict) or 'proof' not in d):
            raise InvalidParameterError('Posted data must be an JSON encoded '
                                        'proof object: '
                                        '{"proof":"...proof object..."}')

        db_contract = lookup_contract(token, file_hash)

        beat = db_contract.token.heartbeat

        try:
            proof = beat.proof_type().fromdict(d['proof'])
        except:
            raise InvalidParameterError('Proof corrupted.')

        if (not verify_proof(token, file_hash, proof, request.remote_addr)):
            raise InvalidParameterError(
                'Invalid proof.')

        response = dict(status='ok')

        if (app.mongo_logger is not None):
            app.mongo_logger.log_event('answer',
                                       {'context': handler.context,
                                        'response': response})

        return jsonify(response)

    return handler.response
