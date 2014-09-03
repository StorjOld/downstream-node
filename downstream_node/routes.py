#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import jsonify

from .startup import app


@app.route('/api/downstream/new/<sjcx_address>')
def api_downstream_new_token(sjcx_address):
    return jsonify(token='dfs9mfa2')


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


@app.route('/api/downstream/challenge/<token>/<file_hash>/<hash_response>')
def api_downstream_answer_chunk_contract(token, file_hash, hash_response):
    return jsonify(status="pass")
    return jsonify(status="fail")
