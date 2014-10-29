#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os
import pickle
import unittest
import io
import base58

import mock
from mock import Mock, patch
from datetime import datetime, timedelta

import heartbeat
from RandomIO import RandomIO

from downstream_node.startup import app, db
from downstream_node import models
from downstream_node import node
from downstream_node import config
from downstream_node.exc import InvalidParameterError, NotFoundError, HttpHandler


class TestDownstreamRoutes(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        db.engine.execute('DROP TABLE IF EXISTS contracts,tokens,addresses,files')
        db.create_all()
        self.testfile = RandomIO().genfile(1000)
        
        self.test_address = base58.b58encode_check(b'\x00'+os.urandom(20))
        address = models.Address(address=self.test_address,crowdsale_balance=20000)
        db.session.add(address)
        db.session.commit()

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,tokens,addresses,files')
        os.remove(self.testfile)
        del self.app
    
    def test_api_index(self):
        r = self.app.get('/')
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['msg'],'ok')

    def test_api_downstream_new(self):
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/api/downstream/new/{0}'.format(self.test_address))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        r_token = r_json['token']
        
        r_type = r_json['type']
        
        self.assertEqual(r_type,app.config['HEARTBEAT'].__name__)
        
        r_beat = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])
        
        token = models.Token.query.filter(models.Token.token==r_token).first()
        
        self.assertEqual(token.token,r_token)
        self.assertEqual(pickle.loads(token.heartbeat).get_public(),r_beat)               
        
    def test_api_downstream_heartbeat(self):
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/api/downstream/new/{0}'.format(self.test_address))
                
        r_json = json.loads(r.data.decode('utf-8'))
        
        r_beat = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])
        
        r_token = r_json['token']
        
        r = self.app.get('/api/downstream/heartbeat/{0}'.format(r_token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        r_beat2 = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])
        
        self.assertEqual(r_beat2, r_beat)
        
        # test nonexistant token
        r = self.app.get('/api/downstream/heartbeat/nonexistenttoken')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        self.assertEqual(r_json['message'], 'Nonexistent token')
        
    def test_api_downstream_chunk(self):
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/api/downstream/new/{0}'.format(self.test_address))
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        r_beat = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])
        
        r_token = r_json['token']
        
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/api/downstream/chunk/{0}'.format(r_token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        r_seed = r_json['seed']
        r_hash = r_json['file_hash']
        
        contents = RandomIO(r_seed).read(app.config['TEST_FILE_SIZE'])
        
        chal = app.config['HEARTBEAT'].challenge_type().fromdict(r_json['challenge'])
        
        self.assertIsInstance(chal,app.config['HEARTBEAT'].challenge_type())
        
        tag = app.config['HEARTBEAT'].tag_type().fromdict(r_json['tag'])
        
        self.assertIsInstance(tag,app.config['HEARTBEAT'].tag_type())
        
        # now form proof...
        f = io.BytesIO(contents)
        proof = r_beat.prove(f,chal,tag)
        
        db_token = models.Token.query.filter(models.Token.token == r_token).first()
        beat = pickle.loads(db_token.heartbeat)
        
        db_file = models.File.query.filter(models.File.hash == r_hash).first()
        
        db_contract = models.Contract.query.filter(models.Contract.token_id == db_token.id,
                                                   models.Contract.file_id == db_file.id).first()
        state = pickle.loads(db_contract.state)
        
        # verify proof
        valid = beat.verify(proof,chal,state)
        
        self.assertTrue(valid)
        
        # and also check error code
        r = self.app.get('/api/downstream/chunk/invalidtoken')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['message'],'Nonexistent token.')
        
    def test_api_downstream_challenge(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address,'test.ip.address')
        
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_contract = node.get_chunk_contract(db_token.token,'test.ip.address')
        
        token = db_token.token
        hash = db_contract.file.hash
    
        r = self.app.get('/api/downstream/challenge/{0}/{1}'.format(token,hash))
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        challenge = app.config['HEARTBEAT'].challenge_type().fromdict(r_json['challenge'])
        
        db_contract = node.lookup_contract(token, hash)
        
        self.assertEqual(challenge,pickle.loads(db_contract.challenge))
        self.assertAlmostEqual(r_json['due'],(db_contract.due-datetime.utcnow()).total_seconds(),delta=0.5)
        
        os.remove(db_contract.file.path)
        
        # test invalid token or hash
        r = self.app.get('/api/downstream/challenge/invalid_token/invalid_hash')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type, 'application/json')
        
    def test_api_downstream_answer(self):
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/api/downstream/new/{0}'.format(self.test_address))
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        beat = app.config['HEARTBEAT'].fromdict(r_json['heartbeat'])
        
        r_token = r_json['token']
        
        with patch('downstream_node.routes.request') as request:
            request.remote_addr = 'test.ip.address'
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                r = self.app.get('/api/downstream/chunk/{0}'.format(r_token))
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        r_seed = r_json['seed']
        r_hash = r_json['file_hash']
        
        contents = RandomIO(r_seed).read(app.config['TEST_FILE_SIZE'])
        
        chal = app.config['HEARTBEAT'].challenge_type().fromdict(r_json['challenge'])
        
        tag = app.config['HEARTBEAT'].tag_type().fromdict(r_json['tag'])
        
        f = io.BytesIO(contents)
        proof = beat.prove(f,chal,tag)
        
        with patch('downstream_node.node.get_ip_location') as p,\
                patch('downstream_node.routes.request') as r:
            r.remote_addr = 'test.ip.address'
            data = {"proof":proof.todict()}
            r.get_json.return_value = data
            p.return_value = dict()
            r = self.app.post('/api/downstream/answer/{0}/{1}'.format(r_token,r_hash),
                              data=json.dumps(data),
                              content_type='application/json')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.content_type,'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['status'],'ok')
        
        # test invalid proof
        
        proof = app.config['HEARTBEAT'].proof_type()()
        
        with patch('downstream_node.node.get_ip_location') as p,\
                patch('downstream_node.routes.request') as r:
            r.remote_addr = 'test.ip.address'
            data = {"proof":proof.todict()}
            r.get_json.return_value = data
            p.return_value = dict()
            r = self.app.post('/api/downstream/answer/{0}/{1}'.format(r_token,r_hash),
                              data=json.dumps(data),
                              content_type='application/json')
        self.assertEqual(r.status_code,400)
        self.assertEqual(r.content_type,'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['message'],'Invalid proof.')
        
        # test corrupt proof
        
        with patch('downstream_node.node.get_ip_location') as p,\
                patch('downstream_node.routes.request') as r:
            r.remote_addr = 'test.ip.address'
            data = {"proof":"invalid proof object"}
            r.get_json.return_value = data
            p.return_value = dict()
            r = self.app.post('/api/downstream/answer/{0}/{1}'.format(r_token,r_hash),
                              data=json.dumps(data),
                              content_type='application/json')
        self.assertEqual(r.status_code,400)
        self.assertEqual(r.content_type,'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['message'],'Proof corrupted.')
        
        # test invalid json
        
        with patch('downstream_node.node.get_ip_location') as p,\
                patch('downstream_node.routes.request') as r:
            r.remote_addr = 'test.ip.address'
            data = "invalid proof object"
            r.get_json.return_value = data
            p.return_value = dict()
            r = self.app.post('/api/downstream/answer/{0}/{1}'.format(r_token,r_hash),
                              data=json.dumps(data),
                              content_type='application/json')
        self.assertEqual(r.status_code,400)

        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['message'],'Posted data must be an JSON encoded \
proof object: {"proof":"...proof object..."}')


class TestDownstreamNodeStatus(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        db.engine.execute('DROP TABLE IF EXISTS contracts,tokens,addresses,files')
        db.create_all()
        
        a0 = models.Address(address='0',crowdsale_balance=20000)
        a1 = models.Address(address='1',crowdsale_balance=20000)
        db.session.add(a0)
        db.session.add(a1)
        db.session.commit()
        
        t0 = models.Token(token='0',
                          address_id=a0.id,
                          heartbeat=b'',
                          ip_address='0',
                          farmer_id='0',
                          hbcount=0,
                          location=pickle.dumps(None))
        t1 = models.Token(token='1',
                          address_id=a1.id,
                          heartbeat=b'',
                          ip_address='1',
                          farmer_id='1',
                          hbcount=1,
                          location=pickle.dumps(None))
        db.session.add(t0)
        db.session.add(t1)
        db.session.commit()
        
        f0 = models.File(hash='0',
                         path='file0',
                         redundancy=1,
                         interval=60,
                         added=datetime.utcnow())
        f1 = models.File(hash='1',
                         path='file1',
                         redundancy=1,
                         interval=60,
                         added=datetime.utcnow())
        f2 = models.File(hash='2',
                         path='file2',
                         redundancy=1,
                         interval=60,
                         added=datetime.utcnow())
        db.session.add(f0)
        db.session.add(f1)
        db.session.add(f2)
        db.session.commit()
        
        c0 = models.Contract(token_id=t0.id,
                             file_id=f0.id,
                             state=b'',
                             challenge=b'',
                             tag_path='tag0',
                             start=datetime.utcnow()-timedelta(minutes=20,seconds=60),
                             due=datetime.utcnow()-timedelta(minutes=20),
                             answered=False,
                             seed='0',
                             size=50)
        c1 = models.Contract(token_id=t1.id,
                             file_id=f1.id,
                             state=b'',
                             challenge=b'',
                             tag_path='tag1',
                             start=datetime.utcnow()-timedelta(seconds=60),
                             due=datetime.utcnow()-timedelta(seconds=1),
                             answered=False,
                             seed='0',
                             size=100)
        c2 = models.Contract(token_id=t1.id,
                             file_id=f2.id,
                             state=b'',
                             challenge=b'',
                             tag_path='tag2',
                             start=datetime.utcnow()-timedelta(seconds=60),
                             due=datetime.utcnow()+timedelta(seconds=60),
                             answered=False,
                             seed='0',
                             size=150)
        db.session.add(c0)
        db.session.add(c1)
        db.session.add(c2)        
        db.session.commit()     
        
    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,tokens,addresses,files')
       
    def test_api_status_list(self):
        r = self.app.get('/api/downstream/status/list/')
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['farmers'][0]['id'],'0')
        self.assertEqual(r_json['farmers'][1]['id'],'1')

    def test_api_status_list_invalid_sort(self):
        r = self.app.get('/api/downstream/status/list/by/invalid.sort')
        
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.content_type,'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['message'],'Invalid sort')

    def test_api_status_list_limit(self):
        r = self.app.get('/api/downstream/status/list/1')
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(len(r_json['farmers']),1)
        self.assertEqual(r_json['farmers'][0]['id'],'0')
        
    def test_api_status_list_limit_page(self):
        r = self.app.get('/api/downstream/status/list/1/1')
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(len(r_json['farmers']),1)
        self.assertEqual(r_json['farmers'][0]['id'],'1')

        
    def test_api_status_list_by_farmer_id(self):
        r = self.app.get('/api/downstream/status/list/by/d/id')
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['farmers'][0]['id'],'1')
        self.assertEqual(r_json['farmers'][1]['id'],'0')

    def generic_list_by(self, string):
        r = self.app.get('/api/downstream/status/list/by/{0}'.format(string))
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['farmers'][0]['id'],'0')
        self.assertEqual(r_json['farmers'][1]['id'],'1')
        
        r = self.app.get('/api/downstream/status/list/by/d/{0}'.format(string))
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['farmers'][0]['id'],'1')
        self.assertEqual(r_json['farmers'][1]['id'],'0')
        
    def test_api_status_list_by_address(self):
        self.generic_list_by('address')
        
    def test_api_status_list_by_uptime(self):
        self.generic_list_by('uptime')
        
    def test_api_status_list_by_heartbeats(self):
        self.generic_list_by('heartbeats')
    
    def test_api_status_list_by_iphash(self):
        pass
    
    def test_api_status_list_by_contracts(self):
        self.generic_list_by('contracts')
        
    def test_api_status_list_by_size(self):
        self.generic_list_by('size')
        
    def test_api_status_list_by_online(self):
        self.generic_list_by('online')

    def test_api_status_show_invalid_id(self):
        r = self.app.get('/api/downstream/status/show/invalidfarmer')
        
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.content_type,'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['message'],'Nonexistant farmer id.')
        
    def test_api_status_show(self):
        r = self.app.get('/api/downstream/status/show/1')
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['id'],'1')
        

class TestDownstreamNodeFuncs(unittest.TestCase):
    def setUp(self):
        db.engine.execute('DROP TABLE IF EXISTS contracts,tokens,addresses,files')
        db.create_all()
        self.testfile = RandomIO().genfile(1000)
            
        self.test_address = base58.b58encode_check(b'\x00'+os.urandom(20))
        
        self.full_location = {'postal': {'code': '95014'}, 
                              'location': {'longitude': -122.0946, 
                                           'metro_code': 807, 
                                           'latitude': 37.3042, 
                                           'time_zone':'America/Los_Angeles'}, 
                              'registered_country': {'iso_code': 'US', 
                                                     'geoname_id': 6252001, 
                                                     'names': {'fr': '\xc9tats-Unis', 
                                                               'de': 'USA', 
                                                               'en': 'United States', 
                                                               'es': 'Estados Unidos', 
                                                               'pt-BR': 'Estados Unidos', 
                                                               'ru': '\u0421\u0448\u0430', 
                                                               'ja': '\u30a2\u30e1\u30ea\u30ab\u5408\u8846\u56fd', 
                                                               'zh-CN': '\u7f8e\u56fd'}}, 
                              'city': {'geoname_id': 5341145, 
                                       'names': {'en':'Cupertino', 
                                                 'ja': '\u30af\u30d1\u30c1\u30fc\u30ce', 
                                                 'ru': '\u041a\u0443\u043f\u0435\u0440\u0442\u0438\u043d\u043e', 
                                                 'fr': 'Cupertino', 'de': 'Cupertino'}}, 
                              'continent': {'geoname_id': 6255149, 
                                            'code': 'NA', 
                                            'names': {'fr': 'Am\xe9rique du Nord', 
                                                      'de': 'Nordamerika', 
                                                      'en': 'North America', 
                                                      'es': 'Norteam\xe9rica', 
                                                      'pt-BR': 'Am\xe9rica do Norte', 
                                                      'ru': '\u0421\u0435\u0432\u0435\u0440\u043d\u0430\u044f \u0410\u043c\u0435\u0440\u0438\u043a\u0430', 
                                                      'ja': '\u5317\u30a2\u30e1\u30ea\u30ab',
                                                      'zh-CN': '\u5317\u7f8e\u6d32'}}, 
                              'country': {'iso_code': 'US', 
                                          'geoname_id': 6252001, 
                                          'names': {'fr': '\xc9tats-Unis', 
                                                    'de': 'USA', 
                                                    'en': 'United States', 
                                                    'es': 'Estados Unidos', 
                                                    'pt-BR': 'Estados Unidos', 
                                                    'ru': '\u0421\u0448\u0430', 
                                                    'ja': '\u30a2\u30e1\u30ea\u30ab\u5408\u8846\u56fd', 
                                                    'zh-CN': '\u7f8e\u56fd'}}, 
                              'subdivisions': [{'iso_code': 'CA', 
                                                'geoname_id':5332921, 
                                                'names': {'fr': 'Californie', 
                                                          'de': 'Kalifornien', 
                                                          'en': 'California', 
                                                          'es': 'California', 
                                                          'pt-BR': 'Calif\xf3rnia', 
                                                          'ru': '\u041a\u0430\u043b\u0438\u0444\u043e\u0440\u043d\u0438\u044f', 
                                                          'ja': '\u30ab\u30ea\u30d5\u30a9\u30eb\u30cb\u30a2\u5dde', 
                                                          'zh-CN': '\u52a0\u5229\u798f\u5c3c\u4e9a\u5dde'}}]}
        self.partial_location = {'continent': {'geoname_id': 6255151, 
                                               'code': 'OC', 
                                               'names': {'fr': 'Oc\xe9anie', 
                                                         'de': 'Ozeanien', 
                                                         'en': 'Oceania', 
                                                         'es':'Ocean\xeda', 
                                                         'pt-BR': 'Oceania', 
                                                         'ru': '\u041e\u043a\u0435\u0430\u043d\u0438\u044f', 
                                                         'ja': '\u30aa\u30bb\u30a2\u30cb\u30a2', 
                                                         'zh-CN': '\u5927\u6d0b\u6d32'}}, 
                                               'location': {'longitude': 133.0, 
                                                            'latitude': -27.0}, 
                                               'country': {'iso_code': 'AU', 
                                                           'geoname_id': 2077456, 
                                                           'names': {'fr': 'Australie', 
                                                                     'de': 'Australien', 
                                                                     'en': 'Australia', 
                                                                     'es': 'Australia', 
                                                                     'pt-BR': 'Austr\xe1lia', 
                                                                     'ru': '\u0410\u0432\u0441\u0442\u0440\u0430\u043b\u0438\u044f', 
                                                                     'ja': '\u30aa\u30fc\u30b9\u30c8\u30e9\u30ea\u30a2', 
                                                                     'zh-CN': '\u6fb3\u5927\u5229\u4e9a'}}, 
                                               'registered_country': {'iso_code': 'AU', 
                                                                      'geoname_id': 2077456, 
                                                                      'names': {'fr': 'Australie', 
                                                                                'de': 'Australien', 
                                                                                'en': 'Australia', 
                                                                                'es': 'Australia', 
                                                                                'pt-BR': 'Austr\xe1lia', 
                                                                                'ru': '\u0410\u0432\u0441\u0442\u0440\u0430\u043b\u0438\u044f', 
                                                                                'ja': '\u30aa\u30fc\u30b9\u30c8\u30e9\u30ea\u30a2', 
                                                                                'zh-CN': '\u6fb3\u5927\u5229\u4e9a'}}}

        self.no_location = dict()
        
        address = models.Address(address=self.test_address,crowdsale_balance=20000)
        db.session.add(address)
        db.session.commit()

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,tokens,addresses,files')
        os.remove(self.testfile)
        pass

    def test_create_token(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address, 'address')
        
        # verify that the info is in the database
        db_token = models.Token.query.filter(models.Token.token==db_token.token).first()
        
        self.assertIsInstance(pickle.loads(db_token.heartbeat),app.config['HEARTBEAT'])
        
    def test_create_token_bad_address(self):
        # test random address
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            with self.assertRaises(InvalidParameterError) as ex:
                db_token = node.create_token('randomaddress','ipaddress')
        
        self.assertEqual(str(ex.exception),'Invalid address given: address is not a valid SJCX address.')
        
    def test_create_token_bad_address(self):
        # test random address
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            with self.assertRaises(InvalidParameterError) as ex:
                db_token = node.create_token(base58.b58encode_check(b'\x00'+os.urandom(20)),'ipaddress')
        
        self.assertEqual(str(ex.exception),'Invalid address given: address must be in whitelist.')
        
    def test_get_ip_location(self):
        with patch('downstream_node.node.maxminddb.Reader') as reader:
            for l in [self.full_location, self.partial_location, self.no_location]:
                reader.return_value = Mock()
                reader.return_value.get.return_value = l
                location = node.get_ip_location('testaddress')
                if ('country' in l):
                    self.assertEqual(location['country'],l['country']['names']['en'])
                else:
                    self.assertIsNone(location['country'])
                if ('subdivisions' in l):
                    self.assertEqual(location['state'],l['subdivisions'][0]['names']['en'])
                else:
                    self.assertIsNone(location['state'])
                if ('city' in l):
                    self.assertEqual(location['city'],l['city']['names']['en'])
                else:
                    self.assertIsNone(location['city'])
                if ('location' in l):
                    self.assertEqual(location['lat'],l['location']['latitude'])
                    self.assertEqual(location['lon'],l['location']['longitude'])
                else:
                    self.assertIsNone(location['lat'])
                    self.assertIsNone(location['lon'])
                if ('postal' in l):
                    self.assertEqual(location['zip'],l['postal']['code'])
                else:
                    self.assertIsNone(location['zip'])

    def test_create_token_duplicate_id(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address,'duplicate')
            with self.assertRaises(InvalidParameterError) as ex:
                db_token = node.create_token(self.test_address, 'duplicate')
            self.assertEqual(str(ex.exception),'Cannot request more than one token '
                                    'per IP address right now.')

    def test_address_resolve(self):
        db_token = node.create_token(self.test_address, '17.0.0.1')
        
        location = pickle.loads(db_token.location)
        
        self.assertEqual(location['country'],self.full_location['country']['names']['en'])
        self.assertEqual(location['state'],self.full_location['subdivisions'][0]['names']['en'])
        self.assertEqual(location['city'],self.full_location['city']['names']['en'])
        self.assertEqual(location['zip'],self.full_location['postal']['code'])
        self.assertEqual(location['lon'],self.full_location['location']['longitude'])
        self.assertEqual(location['lat'],self.full_location['location']['latitude'])
                    
    def test_delete_token(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = self.full_location
            db_token = node.create_token(self.test_address,'test.ip.address2')
        
        t = db_token.token
        
        node.delete_token(db_token.token)
        
        db_token = models.Token.query.filter(models.Token.token==t).first()
        
        self.assertIsNone(db_token)
        
        with self.assertRaises(InvalidParameterError) as ex:
            node.delete_token('nonexistent token')
            
        self.assertEqual(str(ex.exception),'Nonexistent token.')

    def test_add_file(self):
        db_file = node.add_file(self.testfile)
        
        db_file = models.File.query.filter(models.File.hash==db_file.hash).first()
        
        self.assertEqual(db_file.path,self.testfile)
        self.assertEqual(db_file.redundancy,3)
        self.assertEqual(db_file.interval,60)
        
        db.session.delete(db_file)
        db.session.commit()

    def test_remove_file(self):
        # add a file
        db_file = node.add_file(self.testfile)
        
        hash = db_file.hash
        id = db_file.id
        
        # add some contracts for this file
        for j in range(0,3):
            with patch('downstream_node.node.get_ip_location') as p:
                p.return_value = dict()
                db_token = node.create_token(self.test_address,'testaddress{0}'.format(j))
            
            beat = pickle.loads(db_token.heartbeat)
            
            with open(db_file.path,'rb') as f:
                (tag,state) = beat.encode(f)
                
            chal = beat.gen_challenge(state)
            
            contract = models.Contract(token_id = db_token.id,
                                       file_id = db_file.id,
                                       state = pickle.dumps(state),
                                       challenge = pickle.dumps(chal),
                                       due = datetime.utcnow() + timedelta(seconds = db_file.interval))
                                 
            db.session.add(contract)
            db.session.commit()

        # now remove the file
        
        node.remove_file(db_file.hash)
        
        # confirm that there are no files
        
        db_file = models.File.query.filter(models.File.hash == hash).first()
        
        self.assertIsNone(db_file)
        
        # confirm there are no contracts for this file
        
        db_contracts = models.Contract.query.filter(models.Contract.file_id == id).all()
        
        self.assertEqual(len(db_contracts),0)
    
    def test_remove_file_nonexistant(self):
        with self.assertRaises(InvalidParameterError) as ex:
            node.remove_file('nonexsistant hash')
            
        self.assertEqual(str(ex.exception),'File does not exist.  Cannot remove non existant file')
        
    def test_get_chunk_contract(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address,'test.ip.address4')
        
        db_contract = node.get_chunk_contract(db_token.token, 'test.ip.address4')
        
        # prototyping: verify the file it created
        with open(db_contract.file.path,'rb') as f:
            contents = f.read()

        self.assertEqual(RandomIO(db_contract.seed).read(db_contract.size), contents)
        
        # remove file
        os.remove(db_contract.file.path)
        
        # check presence of tag
        self.assertTrue(os.path.isfile(db_contract.tag_path))
        
        # remove tag
        os.remove(db_contract.tag_path)
        
        with self.assertRaises(InvalidParameterError) as ex:
            node.get_chunk_contract('nonexistent token','test.ip.address4')
        
        self.assertEqual(str(ex.exception),'Nonexistent token.')
        
    def test_update_contract_expired(self):
        db_file = node.add_file(self.testfile)
        
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            db_token = node.create_token(self.test_address,'test.ip.address5')

        contract = models.Contract(token_id = db_token.id,
                                   file_id = db_file.id,
                                   state = pickle.dumps('test state'),
                                   challenge = pickle.dumps('test challenge'),
                                   due = datetime.utcnow() - timedelta(seconds = db_file.interval))
                                       
        db.session.add(contract)
        db.session.commit()
        
        with self.assertRaises(InvalidParameterError) as ex:
            node.update_contract(db_token.token, db_file.hash)
            
        self.assertEqual(str(ex.exception),'Contract has expired.')
        
    def test_verify_proof(self):
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = dict()
            other_token = node.create_token(self.test_address,'existing_ip')
            db_token = node.create_token(self.test_address,'test.ip.address6')
        
        db_contract = node.get_chunk_contract(db_token.token,'test.ip.address6')
        
        beat = pickle.loads(db_token.heartbeat)
        
        # get tags
        with open(db_contract.tag_path,'rb') as f:
            tag = pickle.load(f)
        
        chal = pickle.loads(db_contract.challenge)
        
        # generate a proof
        with open(db_contract.file.path,'rb') as f:
            proof = beat.prove(f,chal,tag)
            
        self.assertTrue(node.verify_proof(db_token.token,db_contract.file.hash,proof,'test.ip.address6'))
        self.assertEqual(db_token.ip_address, 'test.ip.address6')
        
        # check ip address resolution failure
        with self.assertRaises(InvalidParameterError) as ex:
            node.verify_proof(db_token.token,db_contract.file.hash,proof,'existing_ip')
        self.assertEqual(str(ex.exception), 'IP Disallowed, another farmer is using this IP address')

        # check nonexistent token
        
        with self.assertRaises(InvalidParameterError) as ex:
            node.verify_proof('invalid token',db_contract.file.hash,proof,'test.ip.address6')
            
        self.assertEqual(str(ex.exception),'Nonexistent token.')
        
        os.remove(db_contract.file.path)
        os.remove(db_contract.tag_path)
        
        # check nonexistent file
        
        with self.assertRaises(InvalidParameterError) as ex:
            node.verify_proof(db_token.token,'invalid file hash',proof,'test.ip.address6')
            
        self.assertEqual(str(ex.exception),'Invalid file hash')
        
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = self.full_location
            db_token = node.create_token(self.test_address,'test.ip.address7')
        
        # check nonexistent contract
        
        db_file = node.add_file(self.testfile)
        
        with self.assertRaises(InvalidParameterError) as ex:
            node.verify_proof(db_token.token,db_file.hash,proof,'test.ip.address7')
            
        self.assertEqual(str(ex.exception),'Contract does not exist.')
        
        # check expiration
        with patch('downstream_node.node.get_ip_location') as p:
            p.return_value = self.full_location
            db_token = node.create_token(self.test_address,'test.ip.address8')
            
        beat = pickle.loads(db_token.heartbeat)
        
        with open(db_file.path,'rb') as f:
            (tag,state) = beat.encode(f)
            
        chal = beat.gen_challenge(state)
        
        db_contract = models.Contract(token_id = db_token.id,
                                      file_id = db_file.id,
                                      state = pickle.dumps(state),
                                      challenge = pickle.dumps(chal),
                                      due = datetime.utcnow()-timedelta(seconds=1))
                             
        db.session.add(db_contract)
        db.session.commit()
        
        with open(db_contract.file.path,'rb') as f:
            proof = beat.prove(f,chal,tag)
        
        with self.assertRaises(InvalidParameterError) as ex:
            node.verify_proof(db_token.token,db_contract.file.hash,proof,'test.ip.address8')
        self.assertEqual(str(ex.exception), 'Answer failed: contract expired.')
        
        node.remove_file(db_file.hash)

       
class TestDownstreamUtils(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        app.config['FILES_PATH'] = 'tests'
        self.testfile = os.path.abspath(os.path.join(config.FILES_PATH,'test.file'))
        with open(self.testfile,'wb+') as f:
            f.write(os.urandom(1000))
        db.engine.execute('DROP TABLE IF EXISTS contracts,tokens,addresses,files')
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
        self.assertEqual(handler.response.status_code,500)

if __name__ == '__main__':
    unittest.main()