#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pickle

from flask import jsonify, request

from .startup import app
from .lib import (create_token, get_chunk_contract,
                  verify_proof,  update_contract,
                  lookup_contract)
from .models import Token
from sqlalchemy import desc
from .exc import InvalidParameterError, NotFoundError, HttpHandler


@app.route('/')
def api_index():
    return jsonify(msg='ok')


@app.route('/api/downstream/status/list/',
           defaults={'d': False, 'sortby': 'id', 'limit': None, 'page': None})
@app.route('/api/downstream/status/list/<int:limit>',
           defaults={'d': False, 'sortby': 'id', 'page': None})
@app.route('/api/downstream/status/list/<int:limit>/<int:page>',
           defaults={'d': False, 'sortby': 'id'})
@app.route('/api/downstream/status/list/by/<sortby>',
           defaults={'d': False, 'limit': None, 'page': None})
@app.route('/api/downstream/status/list/by/d/<sortby>',
           defaults={'d': True, 'limit': None, 'page': None})
@app.route('/api/downstream/status/list/by/<sortby>/<int:limit>',
           defaults={'d': False, 'page': 0})
@app.route('/api/downstream/status/list/by/d/<sortby>/<int:limit>',
           defaults={'d': True, 'page': 0})
@app.route('/api/downstream/status/list/by/<sortby>/<int:limit>/<int:page>',
           defaults={'d': False})
@app.route('/api/downstream/status/list/by/d/<sortby>/<int:limit>/<int:page>',
           defaults={'d': True})
def api_downstream_status_list(d, sortby, limit, page):
    with HttpHandler() as handler:
        sort_map = {'id': Token.farmer_id,
                    'address': Token.addr,
                    'uptime': Token.uptime,
                    'heartbeats': Token.hbcount,
                    'iphash': Token.iphash,
                    'contracts': Token.contract_count,
                    'size': Token.size,
                    'online': Token.online}

        if (sortby not in sort_map):
            raise InvalidParameterError('Invalid sort')

        sort_stmt = sort_map[sortby]
        if (d):
            sort_stmt = desc(sort_stmt)

        farmer_list_query = Token.query.order_by(sort_stmt)

        if (limit is not None):
            farmer_list_query = farmer_list_query.limit(limit)

        if (page is not None):
            farmer_list_query = farmer_list_query.offset(limit*page)

        farmer_list = farmer_list_query.all()

        farmers = list(map(lambda a:
                           dict(id=a.farmer_id,
                                address=a.addr,
                                location=pickle.loads(a.location),
                                uptime=round(a.uptime*100, 2),
                                heartbeats=a.hbcount,
                                iphash=a.iphash,
                                contracts=a.contract_count,
                                size=a.size,
                                online=a.online), farmer_list))

        return jsonify(farmers=farmers)

    return handler.response


@app.route('/api/downstream/status/show/<farmer_id>')
def api_downstream_status_show(farmer_id):
    with HttpHandler() as handler:
        a = Token.query.filter(Token.farmer_id == farmer_id).first()

        if (a is None):
            raise NotFoundError('Nonexistant farmer id.')

        return jsonify(id=a.farmer_id,
                       address=a.addr,
                       location=pickle.loads(a.location),
                       uptime=round(a.uptime*100, 2),
                       heartbeats=a.hbcount,
                       iphash=a.iphash,
                       contracts=a.contract_count,
                       size=a.size,
                       online=a.online)

    return handler.response


@app.route('/api/downstream/new/<sjcx_address>')
def api_downstream_new_token(sjcx_address):
    # generate a new token
    with HttpHandler() as handler:
        db_token = create_token(sjcx_address, request.remote_addr)
        beat = pickle.loads(db_token.heartbeat)
        pub_beat = beat.get_public()
        return jsonify(token=db_token.token,
                       type=type(beat).__name__,
                       heartbeat=pub_beat.todict())

    return handler.response


@app.route('/api/downstream/chunk/<token>')
def api_downstream_chunk_contract(token):
    with HttpHandler() as handler:
        db_contract = get_chunk_contract(token)

        with open(db_contract.tag_path, 'rb') as f:
            tag = pickle.loads(f.read())
        chal = pickle.loads(db_contract.challenge)

        # now since we are prototyping, we can delete the tag and file
        os.remove(db_contract.file.path)
        os.remove(db_contract.tag_path)

        return jsonify(seed=db_contract.seed,
                       size=db_contract.size,
                       file_hash=db_contract.file.hash,
                       challenge=chal.todict(),
                       tag=tag.todict(),
                       expiration=db_contract.expiration.isoformat())

    return handler.response


@app.route('/api/downstream/challenge/<token>/<file_hash>')
def api_downstream_chunk_contract_status(token, file_hash):
    """For prototyping, this will generate a new challenge
    """
    with HttpHandler() as handler:
        db_contract = update_contract(token, file_hash)

        return jsonify(challenge=pickle.loads(db_contract.challenge).todict(),
                       expiration=db_contract.expiration.isoformat())

    return handler.response


@app.route('/api/downstream/answer/<token>/<file_hash>', methods=['POST'])
def api_downstream_challenge_answer(token, file_hash):
    with HttpHandler() as handler:
        d = request.get_json(silent=True)

        if (dict is False or not isinstance(d, dict) or 'proof' not in d):
            raise InvalidParameterError('Posted data must be an JSON encoded '
                                        'proof object: '
                                        '{"proof":"...proof object..."}')

        db_contract = lookup_contract(token, file_hash)

        beat = pickle.loads(db_contract.token.heartbeat)

        try:
            proof = beat.proof_type().fromdict(d['proof'])
        except:
            raise InvalidParameterError('Proof corrupted.')

        if (not verify_proof(token, file_hash, proof)):
            raise InvalidParameterError('Invalid proof, or proof expired.')

        return jsonify(status='ok')

    return handler.response
