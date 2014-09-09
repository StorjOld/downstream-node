#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import hashlib

from flask import jsonify, request, abort

from downstream_node.startup import app
from downstream_node.models import Challenges
from downstream_node.lib import gen_challenges
from downstream_node.lib.utils import query_to_list


@app.route('/')
def api_index():
    return jsonify(msg='ok')


@app.route('/api/downstream/challenges/<filepath>')
def api_downstream_challenge(filepath):
    """

    :param filepath:
    """
    # Make assertions about the request to make sure it's valid.

    # Commenting out while still in development, should be used in prod
    # try:
    #     assert os.path.isfile(os.path.join('/opt/files', filename))
    # except AssertionError:
    #     resp = jsonify(msg="file name is not valid")
    #     resp.status_code = 400
    #     return resp

    # Hardcode filepath to the testfile in tests while in development
    filepath = os.path.abspath(
        os.path.join(
            os.path.split(__file__)[0], '..', 'tests', 'thirty-two_meg.testfile')
    )

    root_seed = hashlib.sha256(os.urandom(32)).hexdigest()
    filename = os.path.split(filepath)[1]

    query = Challenges.query.filter(Challenges.filename == filename)

    if not query.all():
        gen_challenges(filepath, root_seed)
        query = Challenges.query.filter(Challenges.filename == filename)

    return jsonify(challenges=query_to_list(query))


@app.route('/api/downstream/challenges/answer/<filepath>', methods=['GET', 'POST'])
def api_downstream_challenge_answer(filepath):
    # Make assertions about the request to make sure it's valid.
    """

    :param filepath:
    :return:
    """
    try:
        assert request.json
    except AssertionError:
        resp = jsonify(msg="missing request json")
        resp.status_code = 400
        return resp

    try:
        assert ['seed', 'rootseed', 'block', 'response'] in request.json.keys()
    except AssertionError:
        resp = jsonify(msg="missing data")
        resp.status_code = 400
        return resp

    # Commenting out while still in development, should be used in prod
    # try:
    #     assert os.path.isfile(os.path.join('/opt/files', filename))
    # except AssertionError:
    #     resp = jsonify(msg="file name is not valid")
    #     resp.status_code = 400
    #     return resp
    # Hardcode filepath to the testfile in tests while in development
    filepath = os.path.abspath(
        os.path.join(
            os.path.split(__file__)[0], '..', 'tests', 'thirty-two_meg.testfile')
    )

    filename = os.path.split(filepath)[1]
    query = Challenges.query.filter(Challenges.filename == filename)
    challenge = filter(
        lambda x: x.block == request.json.get('block'),
        query.all()
    )

    # Oh, and challenge should only be len of 1, or we gots problems
    try:
        assert len(challenge) == 1
    except AssertionError:
        # And lets assume it's not our problem, but an input problem
        abort(400)

    # TODO: Fix all the things
    # Make a heartbeat thing
    # make new challenges
    # assert answer is correct based on new stuff
    # move on with our lives


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
