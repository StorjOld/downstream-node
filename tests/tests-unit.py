#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os
import pickle
import unittest
import io

from datetime import datetime, timedelta

from heartbeat import Heartbeat
from RandomIO import RandomIO
from downstream_node.startup import app, db
from downstream_node import models
from downstream_node.lib import node
from downstream_node.config import config


class TestDownstreamRoutes(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        db.create_all()
        self.testfile = os.path.abspath(os.path.join(config.FILES_PATH,'test.file'))
        with open(self.testfile,'wb+') as f:
            f.write(os.urandom(1000))
        
        self.test_address = '13FfNS1wu6u7G9ZYQnyxYP1YRntEqAyEJJ'
        address = models.Address(address=self.test_address)
        db.session.add(address)
        db.session.commit()

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,tokens,addresses,files')
        os.remove(self.testfile)
        del self.app

    def test_api_downstream_new(self):
        
        r = self.app.get('/api/downstream/new/{0}'.format(self.test_address))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        print(r_json)
        
        r_token = r_json['token']
        
        r_beat = Heartbeat.fromdict(r_json['heartbeat'])
        
        token = models.Token.query.filter(models.Token.token==r_token).first()
        
        self.assertEqual(token.token,r_token)
        self.assertEqual(pickle.loads(token.heartbeat).get_public(),r_beat)
        
    def test_api_downstream_chunk(self):
        
        r = self.app.get('/api/downstream/new/{0}'.format(self.test_address))
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        r_beat = Heartbeat.fromdict(r_json['heartbeat'])
        
        r_token = r_json['token']
        
        r = self.app.get('/api/downstream/chunk/{0}'.format(r_token))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        r_seed = r_json['seed']
        r_hash = r_json['file_hash']
        
        contents = RandomIO(r_seed).read(100)
        
        chal = Heartbeat.challenge_type().fromdict(r_json['challenge'])
        
        self.assertIsInstance(chal,Heartbeat.challenge_type())
        
        tag = Heartbeat.tag_type().fromdict(r_json['tag'])
        
        self.assertIsInstance(tag,Heartbeat.tag_type())
        
        # now form proof...
        f = io.BytesIO(contents)
        proof = r_beat.prove(f,chal,tag)
        
        token = models.Token.query.filter(models.Token.token == r_token).first()
        beat = pickle.loads(token.heartbeat)
        
        contract = models.Contract.query.filter(models.Contract.token == r_token,
                                                models.Contract.file_hash == r_hash).first()
        state = pickle.loads(contract.state)
        
        # verify proof
        valid = beat.verify(proof,chal,state)
        
        self.assertTrue(valid)

class TestDownstreamNodeFuncs(unittest.TestCase):
    def setUp(self):
        db.create_all()
        self.testfile = os.path.abspath('tests/test.file')
        with open(self.testfile,'wb+') as f:
            f.write(os.urandom(1000))
            
        self.test_address = '13FfNS1wu6u7G9ZYQnyxYP1YRntEqAyEJJ'
        
        address = models.Address(address=self.test_address)
        db.session.add(address)
        db.session.commit()

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,tokens,addresses,files')
        os.remove(self.testfile)
        pass

    def test_create_token(self):
        db_token = node.create_token(self.test_address)
        
        # verify that the info is in the database
        db_token = models.Token.query.filter(models.Token.token==db_token.token).first()
        
        self.assertIsInstance(pickle.loads(db_token.heartbeat),Heartbeat)

    def test_delete_token(self):
        db_token = node.create_token(self.test_address)
        
        t = db_token.token
        
        node.delete_token(db_token.token)
        
        db_token = models.Token.query.filter(models.Token.token==t).first()
        
        self.assertIsNone(db_token)

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
        
        # add some contracts for this file
        for j in range(0,3):
            db_token = node.create_token(self.test_address)
            
            beat = pickle.loads(db_token.heartbeat)
            
            with open(db_file.path,'rb') as f:
                (tag,state) = beat.encode(f)
                
            chal = beat.gen_challenge(state)
            
            contract = models.Contract(token = db_token.token,
                                       file_hash = hash,
                                       state = pickle.dumps(state),
                                       challenge = pickle.dumps(chal),
                                       expiration = datetime.utcnow() + timedelta(seconds = db_file.interval))
                                 
            db.session.add(contract)
            db.session.commit()

        # now remove the file
        
        node.remove_file(db_file.hash)
        
        # confirm that there are no files
        
        q_file = models.File.query.filter(models.File.hash == hash).first()
        
        self.assertIsNone(q_file)
        
        # confirm there are no contracts for this file
        
        q_contracts = models.Contract.query.filter(models.Contract.file_hash == hash).all()
        
        self.assertEqual(len(q_contracts),0)
    
    def test_remove_file_nonexistant(self):
        with self.assertRaises(RuntimeError) as ex:
            node.remove_file('nonexsistant hash')
            
        self.assertEqual(str(ex.exception),'File does not exist.  Cannot remove non existant file')
        
    def test_get_chunk_contract(self):
        db_token = node.create_token(self.test_address)
        
        db_contract = node.get_chunk_contract(db_token.token)
        
        # prototyping: verify the file it created
        with open(db_contract.file.path,'rb') as f:
            contents = f.read()
            
        self.assertEqual(RandomIO(db_contract.seed).read(100), contents)
        
        # remove file
        os.remove(db_contract.file.path)
        
        # check presence of tag
        tag_path = os.path.join(app.config['TAGS_PATH'],db_contract.file_hash)
        self.assertTrue(os.path.isfile(tag_path))
        
        # remove tag
        os.remove(tag_path)

class TestDownstreamUtils(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        app.config['FILES_PATH'] = 'tests'
        self.testfile = os.path.abspath(os.path.join(config.FILES_PATH,'test.file'))
        with open(self.testfile,'wb+') as f:
            f.write(os.urandom(1000))
        db.create_all()

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE contracts,tokens,addresses,files')
        os.remove(self.testfile)
        del self.app


if __name__ == '__main__':
    unittest.main()