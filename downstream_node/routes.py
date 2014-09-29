#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import hashlib

from heartbeat import Heartbeat
from flask import jsonify, request, abort

from werkzeug import utils

from .startup import app
from .config import config
from .models import Challenges,Files,Addresses,Tokens
from .lib import create_token,delete_token,add_file,remove_file
from .lib.utils import query_to_list


@app.route('/')
def api_index():
    return jsonify(msg='ok')

@app.route('/api/downstream/new/<sjcx_address>')
def api_downstream_new_token(sjcx_address):
    # generate a new token
    try:
        (token,beat) = create_token(sjcx_address)
        return jsonify(token=token, heartbeat=beat.todict())
    except Exception as ex:
        return jsonify(status='error',
                       message=str(ex))

@app.route('/api/downstream/chunk/<token>')
def api_downstream_chunk_contract(token):
    return jsonify(status='no_chunks')
    return jsonify(status='no_token')
    return jsonify(status='error')
    return jsonify(status='ok')


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
def api_downstream_challenge_answer(token,file_hash):
    return jsonify(status="pass")
    return jsonify(status="fail")
