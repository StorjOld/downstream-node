#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os
import pickle
import unittest
import io
import base58
import maxminddb

import mock
from mock import Mock, patch
from datetime import datetime, timedelta

import heartbeat
from RandomIO import RandomIO

from downstream_node.startup import app, db, load_heartbeat, load_logger
from downstream_node import models
from downstream_node import node
from downstream_node import config
from downstream_node import uptime
from downstream_node import log
from downstream_node.exc import (InvalidParameterError,
                                 HttpHandler)

app.config[
    'SQLALCHEMY_DATABASE_URI'] = \
    'mysql+pymysql://localhost/test_downstream?charset=utf8'


class TestStartup(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_load_heartbeat_exists(self):
        test_file = 'test_heartbeat'
        with open(test_file, 'wb') as f:
            pickle.dump(app.heartbeat, f)
        beat = load_heartbeat(None,
                              test_file,
                              app.config['HEARTBEAT_CHECK_FRACTION'])
        self.assertEqual(beat, app.heartbeat)
        os.remove(test_file)

    def test_load_heartbeat_construct(self):
        test_file = 'test_heartbeat'
        beat = load_heartbeat(app.config['HEARTBEAT'],
                              test_file,
                              app.config['HEARTBEAT_CHECK_FRACTION'])
        self.assertIsInstance(beat, app.config['HEARTBEAT'])
        with open(test_file, 'rb') as f:
            loaded_beat = pickle.load(f)
        self.assertEqual(loaded_beat, beat)
        os.remove(test_file)

    def test_log_startup_log(self):
        mock_alias = 'mock_alias'
        logger = load_logger(True,
                             app.config['MONGO_URI'],
                             mock_alias)
        self.assertIsInstance(logger, log.mongolog)
        self.assertEqual(logger.server, mock_alias)

    def test_log_startup_none(self):
        mock_uri = 'mock_uri'
        mock_alias = 'mock_alias'
        logger = load_logger(False,
                             mock_uri,
                             mock_alias)
        self.assertIsNone(logger)


class TestDownstreamModels(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        db.engine.execute(
            'DROP TABLE IF EXISTS contracts,chunks,tokens,addresses,files')
        db.create_all()
        self.test_address = base58.b58encode_check(b'\x00' + os.urandom(20))
        address = models.Address(
            address=self.test_address, crowdsale_balance=20000)
        db.session.add(address)
        db.session.commit()
        pass

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,chunks,tokens,addresses,files')
        pass

    def test_uptime_zero(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address, 'test.ip.address')

        self.assertEqual(db_token.online_time, 0)


class TestDownstreamRoutes(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        app.config['REQUIRE_SIGNATURE'] = False
        db.engine.execute(
            'DROP TABLE IF EXISTS contracts,chunks,tokens,addresses,files')
        db.create_all()
        self.testfile = RandomIO().genfile(1000)

        self.test_address = '19qVgG8C6eXwKMMyvVegsi3xCsKyk3Z3jV'
        self.test_signature = ('HyzVUenXXo4pa+kgm1vS8PNJM83eIXFC5r0q86FGbqFcdl'
                               'a6rcw72/ciXiEPfjli3ENfwWuESHhv6K9esI0dl5I=')
        self.test_message = 'test message'
        self.test_size = app.config['DEFAULT_CHUNK_SIZE']
        address = models.Address(
            address=self.test_address, crowdsale_balance=10000)
        db.session.add(address)
        db.session.commit()

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,chunks,tokens,addresses,files')
        os.remove(self.testfile)
        del self.app

    def test_api_index(self):
        r = self.app.get('/')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['msg'], 'ok')

    def test_api_downstream_new(self):
        app.mongo_logger = mock.MagicMock()
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/{0}'.format(self.test_address))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        r_token = r_json['token']

        r_type = r_json['type']

        self.assertEqual(r_type, app.config['HEARTBEAT'].__name__)

        r_beat = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])

        token = models.Token.query.filter(
            models.Token.token == r_token).first()

        self.assertEqual(token.token, r_token)
        self.assertEqual(app.heartbeat.get_public(), r_beat)

    def test_api_downstream_new_signed(self):
        app.config['REQUIRE_SIGNATURE'] = True
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            request.method = 'POST'
            request.get_json.return_value = dict(
                {'signature': self.test_signature,
                 'message': self.test_message})
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/{0}'.format(self.test_address))
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.content_type, 'application/json')

    def test_api_downstream_new_signed_invalid_object(self):
        app.config['REQUIRE_SIGNATURE'] = True
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            request.method = 'POST'
            request.get_json.return_value = dict({'invalid': 'dictionary'})
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/{0}'.format(self.test_address))
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.content_type, 'application/json')

    def test_api_downstream_new_signed_invalid_signature(self):
        app.config['REQUIRE_SIGNATURE'] = True
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            request.method = 'POST'
            request.get_json.return_value = dict(
                {
                    'signature': 'AyzVUenXXo4pa+kgm1vS8PNPM83eIXFC5r0q86FGbqFc'
                    'dla6rcw72/ciXiEPfjli3ENfwWuESHhv6K9esI0dl5I=',
                    'message': self.test_message})
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/{0}'.format(self.test_address))
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.content_type, 'application/json')

    def test_api_downstream_new_signed_too_long(self):
        app.config['REQUIRE_SIGNATURE'] = True
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            request.method = 'POST'
            request.get_json.return_value = dict(
                {
                    'signature': 'HyzVUenXXo4pa+kgm1vS8PNJM83eIXFC5r0q86FGbqFc'
                    'dla6rcw72/ciXiEPfjli3ENfwWuESHhv6K9esI0dl5I=',
                    'message': 'longmessage' *
                    1000})
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/{0}'.format(self.test_address))
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.content_type, 'application/json')

    def test_api_downstream_new_signed_too_short(self):
        app.config['REQUIRE_SIGNATURE'] = True
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            request.method = 'POST'
            request.get_json.return_value = dict(
                {'signature': 'AyzVUenXXo4p', 'message': self.test_message})
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/{0}'.format(self.test_address))
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.content_type, 'application/json')

    def test_api_downstream_new_signed_no_sig(self):
        app.config['REQUIRE_SIGNATURE'] = True
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            request.method = 'GET'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/{0}'.format(self.test_address))
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.content_type, 'application/json')

    def test_api_downstream_new_invalid_address(self):
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/invalidaddress')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, 'application/json')

    def test_api_downstream_heartbeat(self):
        app.mongo_logger = mock.MagicMock()
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/{0}'.format(self.test_address))

        r_json = json.loads(r.data.decode('utf-8'))

        print(r_json['heartbeat'])

        r_beat = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])

        r_token = r_json['token']

        r = self.app.get('/heartbeat/{0}'.format(r_token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        print(r_json['heartbeat'])
        r_beat2 = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])

        self.assertEqual(r_beat2, r_beat)

        # test nonexistant token
        r = self.app.get('/heartbeat/nonexistenttoken')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))
        self.assertEqual(r_json['message'], 'Nonexistent token.')

    def test_api_downstream_chunk(self):
        app.mongo_logger = mock.MagicMock()
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/{0}'.format(self.test_address))

        r_json = json.loads(r.data.decode('utf-8'))

        r_beat = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])

        r_token = r_json['token']

        node.generate_test_file(self.test_size)

        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/chunk/{0}'.format(r_token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        chunk = r_json['chunks'][0]

        r_seed = chunk['seed']
        r_hash = chunk['file_hash']

        contents = RandomIO(r_seed).read(app.config['DEFAULT_CHUNK_SIZE'])

        chal = app.config['HEARTBEAT'].challenge_type().fromdict(
            chunk['challenge'])

        self.assertIsInstance(chal, app.config['HEARTBEAT'].challenge_type())

        tag = app.config['HEARTBEAT'].tag_type().fromdict(chunk['tag'])

        self.assertIsInstance(tag, app.config['HEARTBEAT'].tag_type())

        # now form proof...
        f = io.BytesIO(contents)
        proof = r_beat.prove(f, chal, tag)

        beat = app.heartbeat

        db_contract = models.Contract.query.filter(
            models.Contract.id == r_hash).first()

        state = db_contract.state

        # verify proof
        valid = beat.verify(proof, chal, state)

        self.assertTrue(valid)

        # and also check error code
        r = self.app.get('/chunk/invalidtoken')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['message'], 'Nonexistent token.')

    def test_api_downstream_chunk_contract_no_chunks(self):
        with patch('downstream_node.routes.get_chunk_contracts') as p,\
                patch('downstream_node.routes.process_token_ip_address'),\
                patch('downstream_node.routes.Token') as p3:
            p3.query.filter.return_value.first.return_value = 'dummy_token'
            p.return_value = []
            r = self.app.get('/chunk/test_token')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['chunks'], [])

    def test_api_downstream_challenge(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address, 'test.ip.address')

        node.generate_test_file(self.test_size)

        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_contract = list(
                node.get_chunk_contracts(db_token, self.test_size))[0]

        token = db_token.token
        hash = db_contract.id

        app.mongo_logger = mock.MagicMock()
        r = self.app.get('/challenge/{0}'.format(token))

        self.assertEqual(r.status_code, 200, r.data.decode('utf-8'))
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        challenge = r_json['challenges'][0]

        chal = app.config['HEARTBEAT'].challenge_type().fromdict(
            challenge['challenge'])

        db_contract = models.Contract.query.filter(
            models.Contract.id == hash).first()

        self.assertEqual(chal, db_contract.challenge)
        self.assertAlmostEqual(
            challenge['due'],
            (db_contract.due - datetime.utcnow()).total_seconds(),
            delta=0.5)

        # test invalid token or hash
        r = self.app.get('/challenge/invalid_token')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, 'application/json')

    def test_api_downstream_answer(self):
        app.mongo_logger = mock.MagicMock()
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/new/{0}'.format(self.test_address))

        r_json = json.loads(r.data.decode('utf-8'))

        beat = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])

        r_token = r_json['token']

        chunk = node.generate_test_file(self.test_size)

        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/chunk/{0}'.format(r_token))

        r_json = json.loads(r.data.decode('utf-8'))['chunks'][0]

        r_seed = r_json['seed']
        r_hash = r_json['file_hash']

        contents = RandomIO(r_seed).read(app.config['DEFAULT_CHUNK_SIZE'])

        chal = app.config['HEARTBEAT'].challenge_type().fromdict(
            r_json['challenge'])

        tag = app.config['HEARTBEAT'].tag_type().fromdict(r_json['tag'])

        f = io.BytesIO(contents)
        proof = beat.prove(f, chal, tag)

        with patch('downstream_node.node.get_ip_location') as p,\
                patch('downstream_node.routes.request') as r:
            r.remote_addr = 'test.ip.address'
            data = {'proofs': [
                {'file_hash': r_hash,
                 'proof': proof.todict()}]}
            r.stream = io.BytesIO(json.dumps(data).encode('utf-8'))
            p.return_value = dict()
            r = self.app.post('/answer/{0}'.format(r_token, r_hash),
                              content_type='application/json')
        self.assertEqual(r.status_code, 200, r.data.decode('utf-8'))
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertIn('status', r_json['report'][0], r_json)
        self.assertEqual(r_json['report'][0]['status'], 'ok', r_json)

        # test invalid proof
        # insert a new challenge
        db_contract = models.Contract.query.filter(
            models.Contract.id == r_hash).first()

        node.contract_insert_next_challenge(db_contract)

        proof = app.config['HEARTBEAT'].proof_type()()

        with patch('downstream_node.node.get_ip_location') as p,\
                patch('downstream_node.routes.request') as r:
            r.remote_addr = 'test.ip.address'
            data = {'proofs': [{
                'file_hash': r_hash,
                'proof': proof.todict()}]}
            r.stream = io.BytesIO(json.dumps(data).encode('utf-8'))
            p.return_value = dict()
            r = self.app.post('/answer/{0}'.format(r_token, r_hash),
                              content_type='application/json')
        self.assertEqual(r.status_code, 200, r.data.decode('utf-8'))
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['report'][0]['error'], 'Invalid proof')

        # test corrupt proof

        with patch('downstream_node.node.get_ip_location') as p,\
                patch('downstream_node.routes.request') as r:
            r.remote_addr = 'test.ip.address'
            data = {'proofs': [{'file_hash': r_hash,
                                'proof': "invalid proof object"}]}
            r.stream = io.BytesIO(json.dumps(data).encode('utf-8'))
            p.return_value = dict()
            r = self.app.post('/answer/{0}'.format(r_token, r_hash),
                              content_type='application/json')
        self.assertEqual(r.status_code, 200, r.data.decode('utf-8'))
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['report'][0]['error'], 'Proof corrupted')

        # test invalid json

        with patch('downstream_node.node.get_ip_location') as p,\
                patch('downstream_node.routes.request') as r:
            r.remote_addr = 'test.ip.address'
            data = 'invalid proof object'
            r.stream = io.BytesIO(data.encode('utf-8'))
            p.return_value = dict()
            r = self.app.post('/answer/{0}'.format(r_token, r_hash),
                              content_type='application/json')
        self.assertEqual(r.status_code, 200)

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['report'], [])


class TestDownstreamNodeStatus(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        db.engine.execute(
            'DROP TABLE IF EXISTS contracts,chunks,tokens,addresses,files')
        db.create_all()
        
        self.assertEqual(db.session.query(models.Token).count(), 0)
        print('Token count correct during setup.')

        self.a0 = models.Address(address='0', crowdsale_balance=20000)
        a1 = models.Address(address='1', crowdsale_balance=20000)
        db.session.add(self.a0)
        db.session.add(a1)
        db.session.commit()

        t0 = models.Token(token='0',
                          address_id=self.a0.id,
                          ip_address='0',
                          farmer_id='0',
                          hbcount=0,
                          location=None)
        t1 = models.Token(token='1',
                          address_id=a1.id,
                          ip_address='1',
                          farmer_id='1',
                          hbcount=1,
                          location=None)
        db.session.add(t0)
        db.session.add(t1)
        db.session.commit()

        f0 = models.File(hash='0',
                         path='file0',
                         redundancy=1,
                         interval=60,
                         added=datetime.utcnow(),
                         seed='0',
                         size=50)
        f1 = models.File(hash='1',
                         path='file1',
                         redundancy=1,
                         interval=60,
                         added=datetime.utcnow(),
                         seed='0',
                         size=100)
        f2 = models.File(hash='2',
                         path='file2',
                         redundancy=1,
                         interval=60,
                         added=datetime.utcnow(),
                         seed='0',
                         size=150)
        db.session.add(f0)
        db.session.add(f1)
        db.session.add(f2)
        db.session.commit()

        c0 = models.Contract(token_id=t0.id,
                             file_id=f0.id,
                             state=b'',
                             challenge=b'',
                             tag_path='tag0',
                             start=datetime.utcnow() -
                             timedelta(minutes=20, seconds=60),
                             due=datetime.utcnow() - timedelta(minutes=20),
                             answered=False)
        c1 = models.Contract(token_id=t1.id,
                             file_id=f1.id,
                             state=b'',
                             challenge=b'',
                             tag_path='tag1',
                             start=datetime.utcnow() - timedelta(seconds=60),
                             due=datetime.utcnow() - timedelta(seconds=1),
                             answered=False)
        c2 = models.Contract(token_id=t1.id,
                             file_id=f2.id,
                             state=b'',
                             challenge=b'',
                             tag_path='tag2',
                             start=datetime.utcnow() - timedelta(seconds=60),
                             due=datetime.utcnow() + timedelta(seconds=60),
                             answered=False)
        db.session.add(c0)
        db.session.add(c1)
        db.session.add(c2)
        db.session.commit()

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,chunks,tokens,addresses,files')

    def test_api_status_list(self):
        r = self.app.get('/status/list/')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['farmers'][0]['id'], '0', 'unexpected returned json: {0}'.format(r_json))
        self.assertEqual(r_json['farmers'][1]['id'], '1', 'unexpected returned json: {0}'.format(r_json))

    def test_api_status_list_invalid_sort(self):
        r = self.app.get('/status/list/by/invalid.sort')

        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['message'], 'Invalid sort.')

    def test_api_status_list_online(self):
        r = self.app.get('/status/list/online/')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(len(r_json['farmers']), 1, 'unexpected returned json: {0}'.format(r_json))
        self.assertEqual(r_json['farmers'][0]['id'], '1', 'unexpected returned json: {0}'.format(r_json))

    def test_api_status_list_limit(self):
        r = self.app.get('/status/list/1')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(len(r_json['farmers']), 1, 'unexpected returned json: {0}'.format(r_json))
        self.assertEqual(r_json['farmers'][0]['id'], '0', 'unexpected returned json: {0}'.format(r_json))

    def test_api_status_list_limit_page(self):
        r = self.app.get('/status/list/1/1')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(len(r_json['farmers']), 1, 'unexpected returned json: {0}'.format(r_json))
        self.assertEqual(r_json['farmers'][0]['id'], '1', 'unexpected returned json: {0}'.format(r_json))

    def test_api_status_list_by_farmer_id(self):
        r = self.app.get('/status/list/by/d/id')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['farmers'][0]['id'], '1', 'unexpected returned json: {0}'.format(r_json))
        self.assertEqual(r_json['farmers'][1]['id'], '0', 'unexpected returned json: {0}'.format(r_json))

    def generic_list_by(self, string):
        r = self.app.get('/status/list/by/{0}'.format(string))

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['farmers'][0]['id'], '0', 'unexpected returned json: {0}'.format(r_json))
        self.assertEqual(r_json['farmers'][1]['id'], '1', 'unexpected returned json: {0}'.format(r_json))

        r = self.app.get('/status/list/by/d/{0}'.format(string))

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['farmers'][0]['id'], '1', 'unexpected returned json: {0}'.format(r_json))
        self.assertEqual(r_json['farmers'][1]['id'], '0', 'unexpected returned json: {0}'.format(r_json))

    def test_api_status_list_by_address(self):
        self.generic_list_by('address')

    def test_api_status_list_by_heartbeats(self):
        self.generic_list_by('heartbeats')

    def test_api_status_list_by_contracts(self):
        self.generic_list_by('contracts')

    def test_api_status_list_by_size(self):
        self.generic_list_by('size')

    def test_api_status_list_by_online(self):
        self.generic_list_by('online')

    def test_api_status_list_by_uptime(self):
        self.generic_list_by('uptime')

    def test_api_status_list_empty_token(self):

        t2 = models.Token(token='2',
                          address_id=self.a0.id,
                          ip_address='2',
                          farmer_id='2',
                          hbcount=0,
                          location=None)
        db.session.add(t2)
        db.session.commit()

        r = self.app.get('/status/list/by/uptime')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(len(r_json['farmers']), 3, 'unexpected returned json: {0}'.format(r_json))
        self.assertEqual(r_json['farmers'][0]['uptime'], 0.0, 'unexpected returned json: {0}'.format(r_json))

    def test_api_status_list_by_uptime_limit(self):
        r = self.app.get('/status/list/by/uptime/1')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(len(r_json['farmers']), 1, 'unexpected returned json: {0}'.format(r_json))
        self.assertEqual(r_json['farmers'][0]['id'], '0', 'unexpected returned json: {0}'.format(r_json))

    def test_api_status_list_by_uptime_limit_page(self):
        r = self.app.get('/status/list/by/uptime/1/1')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(len(r_json['farmers']), 1, 'unexpected returned json: {0}'.format(r_json))
        self.assertEqual(r_json['farmers'][0]['id'], '1', 'unexpected returned json: {0}'.format(r_json))

    def test_api_status_show_invalid_id(self):
        r = self.app.get('/status/show/invalidfarmer')

        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['message'], 'Nonexistant farmer id.')

    def test_api_status_show(self):
        r = self.app.get('/status/show/1')

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['id'], '1')


class TestDownstreamNodeFuncs(unittest.TestCase):

    def setUp(self):
        db.engine.execute(
            'DROP TABLE IF EXISTS contracts,chunks,tokens,addresses,files')
        db.create_all()
        self.test_size = 1000
        self.test_seed = 'test seed'
        self.testfile = RandomIO().genfile(1000)

        self.test_address = base58.b58encode_check(b'\x00' + os.urandom(20))
        reader = maxminddb.Reader(app.config['MMDB_PATH'])
        self.full_location = reader.get('17.0.0.1')
        self.partial_location = {
            'continent': {
                'geoname_id': 6255151,
                'code': 'OC',
                'names': {
                    'fr': 'Oc\xe9anie',
                    'de': 'Ozeanien',
                    'en': 'Oceania',
                    'es': 'Ocean\xeda',
                    'pt-BR': 'Oceania',
                    'ru': '\u041e\u043a\u0435\u0430\u043d\u0438\u044f',
                    'ja': '\u30aa\u30bb\u30a2\u30cb\u30a2',
                    'zh-CN': '\u5927\u6d0b\u6d32'}},
            'location': {
                'longitude': 133.0,
                'latitude': -27.0},
            'country': {
                'iso_code': 'AU',
                'geoname_id': 2077456,
                'names': {
                    'fr': 'Australie',
                    'de': 'Australien',
                    'en': 'Australia',
                    'es': 'Australia',
                    'pt-BR': 'Austr\xe1lia',
                    'ru': '\u0410\u0432\u0441\u0442\u0440\u0430\u043b\u0438'
                    '\u044f',
                    'ja': '\u30aa\u30fc\u30b9\u30c8\u30e9\u30ea\u30a2',
                    'zh-CN': '\u6fb3\u5927\u5229\u4e9a'}},
            'registered_country': {
                'iso_code': 'AU',
                            'geoname_id': 2077456,
                            'names': {
                                'fr': 'Australie',
                                'de': 'Australien',
                                'en': 'Australia',
                                'es': 'Australia',
                                'pt-BR': 'Austr\xe1lia',
                                'ru': '\u0410\u0432\u0441\u0442\u0440\u0430'
                                '\u043b\u0438\u044f',
                                'ja': '\u30aa\u30fc\u30b9\u30c8\u30e9\u30ea'
                                '\u30a2',
                                'zh-CN': '\u6fb3\u5927\u5229\u4e9a'}}}

        self.no_location = dict()

        address = models.Address(
            address=self.test_address, crowdsale_balance=20000)
        db.session.add(address)
        db.session.commit()

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,chunks,tokens,addresses,files')
        os.remove(self.testfile)
        pass

    def test_process_token_ip_address_change_ip(self):
        with patch('downstream_node.node.assert_ip_allowed_one_more_token')\
                as a, patch('downstream_node.node.get_ip_location') as b,\
                patch('downstream_node.node.db.session.add'):
            db_token = mock.MagicMock()
            db_token.ip_address = 'old_ip_address'
            new_ip = 'new_ip_address'
            b.return_value = 'test location'
            node.process_token_ip_address(db_token, new_ip, change=True)
            a.assert_called_with(new_ip)
            b.assert_called_with(new_ip)
            self.assertEqual(db_token.location, b.return_value)
            self.assertEqual(db_token.ip_address, new_ip)

    def test_create_token(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address, 'address')

        # verify that the info is in the database
        db_token = models.Token.query.filter(
            models.Token.token == db_token.token).first()

        self.assertIsNotNone(db_token)
        self.assertEqual(db_token.address.address, self.test_address)

    def test_create_token_bad_address(self):
        # test random address
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            with self.assertRaises(InvalidParameterError) as ex:
                node.create_token('randomaddress', 'ipaddress')

        self.assertEqual(
            str(ex.exception),
            'Invalid address given: address is not a valid SJCX address.')

    def test_create_token_invalid_address(self):
        # test random address
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            with self.assertRaises(InvalidParameterError) as ex:
                node.create_token(
                    base58.b58encode_check(
                        b'\x00' +
                        os.urandom(20)),
                    'ipaddress')

        self.assertEqual(
            str(ex.exception),
            'Invalid address given: address must be in whitelist.')

    def test_get_ip_location(self):
        with patch('downstream_node.node.maxminddb.Reader') as reader:
            for l in [self.full_location, self.partial_location,
                      self.no_location]:
                reader.return_value = Mock()
                reader.return_value.get.return_value = l
                location = node.get_ip_location('testaddress')
                if ('country' in l):
                    self.assertEqual(
                        location['country'], l['country']['names']['en'])
                else:
                    self.assertIsNone(location['country'])
                if ('subdivisions' in l):
                    self.assertEqual(
                        location['state'], l['subdivisions'][0]['names']['en'])
                else:
                    self.assertIsNone(location['state'])
                if ('city' in l):
                    self.assertEqual(
                        location['city'], l['city']['names']['en'])
                else:
                    self.assertIsNone(location['city'])
                if ('location' in l):
                    self.assertEqual(
                        location['lat'], l['location']['latitude'])
                    self.assertEqual(
                        location['lon'], l['location']['longitude'])
                else:
                    self.assertIsNone(location['lat'])
                    self.assertIsNone(location['lon'])
                if ('postal' in l):
                    self.assertEqual(location['zip'], l['postal']['code'])
                else:
                    self.assertIsNone(location['zip'])

    def test_create_token_duplicate_id(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            for i in range(0, app.config['MAX_TOKENS_PER_IP']):
                node.create_token(self.test_address, 'duplicate')
            with self.assertRaises(InvalidParameterError) as ex:
                node.create_token(self.test_address, 'duplicate')
            self.assertEqual(
                str(ex.exception),
                'IP Disallowed, only {0} tokens are permitted per IP address'.
                format(app.config['MAX_TOKENS_PER_IP']))

    def test_address_resolve(self):
        db_token = node.create_token(self.test_address, '17.0.0.1')

        location = db_token.location

        self.assertEqual(
            location['country'], self.full_location['country']['names']['en'])
        self.assertEqual(
            location['state'],
            self.full_location['subdivisions'][0]['names']['en'])
        self.assertEqual(
            location['city'], self.full_location['city']['names']['en'])
        self.assertEqual(location['zip'], self.full_location['postal']['code'])
        self.assertEqual(
            location['lon'], self.full_location['location']['longitude'])
        self.assertEqual(
            location['lat'], self.full_location['location']['latitude'])

    def test_delete_token(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = self.full_location
            db_token = node.create_token(self.test_address, 'test.ip.address2')

        t = db_token.token

        node.delete_token(db_token.token)

        db_token = models.Token.query.filter(models.Token.token == t).first()

        self.assertIsNone(db_token)

        with self.assertRaises(InvalidParameterError) as ex:
            node.delete_token('nonexistent token')

        self.assertEqual(str(ex.exception), 'Nonexistent token.')

    def test_add_file(self):
        db_file = node.add_file(self.test_seed, self.test_size)

        db_file = models.File.query.filter(
            models.File.hash == db_file.hash).first()

        self.assertEqual(db_file.seed, self.test_seed)
        self.assertEqual(db_file.size, self.test_size)
        self.assertEqual(db_file.redundancy, 3)
        self.assertEqual(db_file.interval, app.config['DEFAULT_INTERVAL'])

        db.session.delete(db_file)
        db.session.commit()

    def test_remove_file(self):
        # add a file
        db_file = node.add_file(self.test_seed, self.test_size)

        hash = db_file.hash
        id = db_file.id

        # add some contracts for this file
        for j in range(0, 3):
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                db_token = node.create_token(
                    self.test_address, 'testaddress{0}'.format(j))

            beat = app.heartbeat

            f = RandomIO(self.test_seed, self.test_size)

            (tag, state) = beat.encode(f)

            chal = beat.gen_challenge(state)

            contract = models.Contract(
                token_id=db_token.id,
                file_id=db_file.id,
                state=state,
                challenge=chal,
                due=datetime.utcnow() +
                timedelta(
                    seconds=db_file.interval))

            db.session.add(contract)
            db.session.commit()

        # now remove the file

        node.remove_file(db_file.hash)

        # confirm that there are no files

        db_file = models.File.query.filter(models.File.hash == hash).first()

        self.assertIsNone(db_file)

        # confirm there are no contracts for this file

        db_contracts = models.Contract.query.filter(
            models.Contract.file_id == id).all()

        self.assertEqual(len(db_contracts), 0)

    def test_remove_file_nonexistant(self):
        with self.assertRaises(InvalidParameterError) as ex:
            node.remove_file('nonexsistant hash')

        self.assertEqual(
            str(ex.exception),
            'File does not exist.  Cannot remove non existant file')

    def test_get_chunk_contracts(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address, 'test.ip.address4')

        db_chunk = node.generate_test_file(self.test_size)

        db_contracts = list(node.get_chunk_contracts(db_token, self.test_size))

        self.assertEqual(len(db_contracts), 1)

        db_contract = db_contracts[0]

        self.assertEqual(db_contract.file, db_chunk.file)

        # check presence of tag
        self.assertTrue(
            os.path.isfile(
                node.get_local_tag_path(
                    db_contract.tag_path)))

        # remove tag
        os.remove(node.get_local_tag_path(db_contract.tag_path))

    def test_get_chunk_contracts_limited_by_max_size(self):
        app.config['MAX_SIZE_PER_ADDRESS'] = self.test_size
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address, 'test.ip.address')

        node.generate_test_file(self.test_size)
        db_chunk2 = node.generate_test_file(self.test_size)

        db_contracts = list(
            node.get_chunk_contracts(
                db_token,
                2 *
                self.test_size))

        self.assertEqual(len(db_contracts), 1)

        self.assertEqual(db_contracts[0].file.size, self.test_size)

        os.remove(node.get_local_tag_path(db_contracts[0].tag_path))
        os.remove(node.get_local_tag_path(db_chunk2.tag_path))

    def test_update_contract_expired(self):
        db_file = node.add_file(self.test_seed, self.test_size)

        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address, 'test.ip.address5')

        contract = models.Contract(
            token_id=db_token.id,
            file_id=db_file.id,
            state='test state',
            challenge='test challenge',
            due=datetime.utcnow() -
            timedelta(
                seconds=db_file.interval))

        db.session.add(contract)
        db.session.commit()

        with self.assertRaises(InvalidParameterError) as ex:
            node.update_contract(contract)

        self.assertEqual(str(ex.exception), 'Contract has expired.')

    def add_test_token(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address, 'test.ip.address')

        db.session.add(db_token)
        db.session.commit()

        return db_token

    def add_test_file(self):
        db_file = node.add_file(self.test_seed, self.test_size)

        db.session.add(db_file)
        db.session.commit()

        return db_file

    def add_test_contract(self):
        db_file = self.add_test_file()
        db_token = self.add_test_token()

        db_contract = models.Contract(token_id=db_token.id,
                                      file_id=db_file.id,
                                      state='test state',
                                      challenge='test challenge',
                                      due=datetime.utcnow() +
                                      timedelta(seconds=1))

        db.session.add(db_contract)
        db.session.commit()

        return db_contract

    def test_contract_insert_next_challenge_fail(self):
        db_contract = self.add_test_contract()

        with patch('downstream_node.node.app.heartbeat') as beat_patch:
            beat_patch.gen_challenge = mock.MagicMock()
            beat_patch.gen_challenge.side_effect = heartbeat.HeartbeatError(
                'test error')
            self.assertFalse(node.contract_insert_next_challenge(db_contract))

    def test_get_chunk_contracts_no_chunks(self):
        db_token = self.add_test_token()

        db_contracts = list(node.get_chunk_contracts(db_token, 100))

        self.assertEqual(len(db_contracts), 0)

    def add_test_chunk(self):
        db_chunk = node.generate_test_file(self.test_size)

        return db_chunk

    def test_get_chunk_contracts_init_failed(self):
        db_token = self.add_test_token()
        self.add_test_chunk()

        with patch('downstream_node.node.contract_insert_next_challenge') as p:
            p.return_value = False
            contracts = list(
                node.get_chunk_contracts(db_token, self.test_size))
            self.assertEqual(len(contracts), 0)

    def test_update_contract_no_more_challenges(self):
        db_contract = self.add_test_contract()

        db_contract.due = datetime.utcnow() - timedelta(seconds=1)
        db_contract.answered = True

        with patch('downstream_node.node.contract_insert_next_challenge') as p:
            p.return_value = False
            db_contract = node.update_contract(db_contract)

        self.assertIsNone(db_contract)


class TestDownstreamUtils(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        app.config['FILES_PATH'] = 'tests'
        self.testfile = os.path.abspath(
            os.path.join(config.FILES_PATH, 'test.file'))
        with open(self.testfile, 'wb+') as f:
            f.write(os.urandom(1000))
        db.engine.execute(
            'DROP TABLE IF EXISTS contracts,chunks,tokens,addresses,files')
        db.create_all()

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,tokens,addresses,files')
        os.remove(self.testfile)
        del self.app


class TestDownstreamException(unittest.TestCase):

    def test_general_exception(self):
        with patch('downstream_node.exc.jsonify') as mock:
            with HttpHandler() as handler:
                raise Exception('test exception')
        mock.assert_called_with(status='error',
                                message='Internal Server Error')
        self.assertEqual(handler.response.status_code, 500)


class TestDownstreamHttpHandler(unittest.TestCase):

    def test_logging(self):
        logger = mock.MagicMock()
        test_exception = Exception('test exception')
        with patch('downstream_node.exc.jsonify'),\
                HttpHandler(logger) as handler:
            raise test_exception

        logger.log_exception.assert_called_with(
            test_exception, handler.context)


class TestDownstreamNodeLog(unittest.TestCase):

    def test_init(self):
        test_uri = 'uri'
        test_alias = 'alias'
        with patch('pymongo.MongoClient') as p:
            test_log = log.mongolog(test_uri, test_alias)

        client = p.return_value
        client.get_default_database.assert_called_with()
        db = client.get_default_database.return_value
        self.assertEqual(test_log.db, db)
        self.assertEqual(test_log.events, db.events)
        self.assertEqual(test_log.server, test_alias)

    def test_log_exception(self):
        with patch('pymongo.MongoClient'):
            test_log = log.mongolog('uri')
            with patch.object(log.mongolog, 'log_event') as m:
                test_exception = Exception('test exception')
                test_log.log_exception(test_exception, 'test context')
                m.assert_called_with('exception',
                                     {'type': type(test_exception).__name__,
                                      'value': str(test_exception),
                                         'context': 'test context'})

    def test_log_event(self):
        with patch('pymongo.MongoClient'),\
                patch('downstream_node.log.datetime') as dt:
            test_log = log.mongolog('uri')
            test_time = 'test time'
            dt.datetime.utcnow.return_value = test_time
            test_log.log_event('test type', 'test value')
            test_event = {'time': test_time,
                          'type': 'test type',
                          'value': 'test value',
                          'server': test_log.server}
            test_log.events.insert.assert_called_with(test_event)


class MockUptimeContract(object):
    static_id = 0

    def __init__(self, start, expiration, cached=False):
        self.id = MockUptimeContract.static_id
        MockUptimeContract.static_id += 1
        self.start = start
        self.expiration = expiration
        self.cached = cached


class TestUptimeCalculator(unittest.TestCase):

    def test_base(self):
        now = datetime.utcnow()
        contract1 = MockUptimeContract(
            now - timedelta(seconds=120), now - timedelta(seconds=60))
        contract2 = MockUptimeContract(now - timedelta(seconds=60), now)
        contract3 = MockUptimeContract(
            now + timedelta(seconds=60), now + timedelta(seconds=120))

        uncached = [contract1, contract2, contract3]

        us = uptime.UptimeSummary()

        uc = uptime.UptimeCalculator(uncached, us)

        summary = uc.update()

        self.assertAlmostEqual(summary.uptime.total_seconds(), 120)

    def test_fraction(self):
        now = datetime.utcnow()
        contract1 = MockUptimeContract(
            now - timedelta(seconds=120), now - timedelta(seconds=60))

        uncached = [contract1]

        us = uptime.UptimeSummary(contract1.start)

        uc = uptime.UptimeCalculator(uncached, us)

        with patch('downstream_node.uptime.datetime') as p:
            p.utcnow.return_value = now
            summary = uc.update()

        self.assertEqual(uc.summary.uptime, timedelta(seconds=60))
        self.assertEqual(uc.summary.start, contract1.start)
        self.assertEqual(summary.fraction(), 0.5)

    def test_many_contracts(self):
        now = datetime.utcnow()
        contract1 = MockUptimeContract(
            now - timedelta(seconds=120), now - timedelta(seconds=60))
        contract2 = MockUptimeContract(
            now - timedelta(seconds=120), now - timedelta(seconds=60))
        contract3 = MockUptimeContract(
            now - timedelta(seconds=120), now - timedelta(seconds=60))
        contract4 = MockUptimeContract(
            now - timedelta(seconds=120), now - timedelta(seconds=60))
        contract5 = MockUptimeContract(
            now - timedelta(seconds=120), now - timedelta(seconds=60))

        uncached = [contract1, contract2, contract3, contract4, contract5]

        summary = uptime.UptimeCalculator(uncached).update()

        self.assertEqual(summary.uptime.total_seconds(), 60)

if __name__ == '__main__':
    unittest.main()
