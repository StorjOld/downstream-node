#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pickle

from flask import jsonify

from .startup import app
from .lib import create_token, get_chunk_contract


@app.route('/')
def api_index():
    return jsonify(msg='ok')


@app.route('/api/downstream/new/<sjcx_address>')
def api_downstream_new_token(sjcx_address):
    # generate a new token
    try:
        db_token = create_token(sjcx_address)
        pub_beat = pickle.loads(db_token.heartbeat).get_public()
        return jsonify(token=db_token.token,
                       heartbeat=pub_beat.todict())
    except Exception as ex:
        return jsonify(status='error',
                       message=str(ex))


@app.route('/api/downstream/chunk/<token>')
def api_downstream_chunk_contract(token):
    try:
        db_contract = get_chunk_contract(token)
        tag_path = os.path.join(app.config['TAGS_PATH'],
                                db_contract.file.hash)
        with open(tag_path, 'rb') as f:
            tag = pickle.loads(f.read())
        chal = pickle.loads(db_contract.challenge)

        return jsonify(seed=db_contract.seed,
                       file_hash=db_contract.file_hash,
                       challenge=chal.todict(),
                       tag=tag.todict(),
                       expiration=db_contract.expiration)

    except Exception as ex:
        return jsonify(status='error',
                       message=str(ex))


@app.route('/api/downstream/remove/<token>/<file_hash>', methods=['DELETE'])
def api_downstream_end_contract(token, file_hash):
    return jsonify(status='no_token')
    return jsonify(status='no_hash')
    return jsonify(status='error')
    return jsonify(status='ok')


@app.route('/api/downstream/due/<account_token>')
def api_downstream_chunk_contract_status(account_token):
    return jsonify(contracts="data")


@app.route('/api/downstream/answer/<token>/<file_hash>', methods=['POST'])
def api_downstream_challenge_answer(token, file_hash):
    return jsonify(status="pass")
    return jsonify(status="fail")
