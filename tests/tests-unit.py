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
        self.testfile = RandomIO().genfile(1000)
        
        self.test_address = '13FfNS1wu6u7G9ZYQnyxYP1YRntEqAyEJJ'
        address = models.Address(address=self.test_address)
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
        
        # assert that we can add any address
        r = self.app.get('/api/downstream/new/1J29dwrT4UBkW6R8dq6qocBXQwHHzB2NHS')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        # assert address has to be valid
        r = self.app.get('/api/downstream/new/nonexistentaddress')
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['message'],'Invalid address given.')
        
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
        
        contents = RandomIO(r_seed).read(app.config['TEST_FILE_SIZE'])
        
        chal = Heartbeat.challenge_type().fromdict(r_json['challenge'])
        
        self.assertIsInstance(chal,Heartbeat.challenge_type())
        
        tag = Heartbeat.tag_type().fromdict(r_json['tag'])
        
        self.assertIsInstance(tag,Heartbeat.tag_type())
        
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
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['message'],'Invalid token given.')
        
    def test_api_downstream_challenge(self):
        db_token = node.create_token(self.test_address)
        
        db_contract = node.get_chunk_contract(db_token.token)
    
        r = self.app.get('/api/downstream/challenge/{0}/{1}'.format(db_token.token,db_contract.file.hash))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        challenge = Heartbeat.challenge_type().fromdict(r_json['challenge'])
        
        self.assertEqual(challenge,pickle.loads(db_contract.challenge))
        self.assertEqual(datetime.strptime(r_json['expiration'],'%Y-%m-%dT%H:%M:%S'),db_contract.expiration)
        
        os.remove(db_contract.file.path)
        
        # test invalid token or hash
        r = self.app.get('/api/downstream/challenge/invalid_token/invalid_hash')
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.content_type, 'application/json')
        
    def test_api_downstream_answer(self):
        r = self.app.get('/api/downstream/new/{0}'.format(self.test_address))
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        beat = Heartbeat.fromdict(r_json['heartbeat'])
        
        r_token = r_json['token']
        
        r = self.app.get('/api/downstream/chunk/{0}'.format(r_token))
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        r_seed = r_json['seed']
        r_hash = r_json['file_hash']
        
        contents = RandomIO(r_seed).read(app.config['TEST_FILE_SIZE'])
        
        chal = Heartbeat.challenge_type().fromdict(r_json['challenge'])
        
        tag = Heartbeat.tag_type().fromdict(r_json['tag'])
        
        f = io.BytesIO(contents)
        proof = beat.prove(f,chal,tag)
        
        r = self.app.post('/api/downstream/answer/{0}/{1}'.format(r_token,r_hash),
                          data=json.dumps({"proof":proof.todict()}),
                          content_type='application/json')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.content_type,'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['status'],'ok')
        
        # test invalid proof
        
        proof = Heartbeat.proof_type()()
        
        r = self.app.post('/api/downstream/answer/{0}/{1}'.format(r_token,r_hash),
                          data=json.dumps({"proof":proof.todict()}),
                          content_type='application/json')
        self.assertEqual(r.status_code,500)
        self.assertEqual(r.content_type,'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['message'],'Invalid proof, or proof expired.')
        
        # test corrupt proof
        
        r = self.app.post('/api/downstream/answer/{0}/{1}'.format(r_token,r_hash),
                          data=json.dumps({"proof":"invalid proof object"}),
                          content_type='application/json')
        self.assertEqual(r.status_code,500)
        self.assertEqual(r.content_type,'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))

        self.assertEqual(r_json['message'],'Proof corrupted.')
        
        # test invalid json
        
        r = self.app.post('/api/downstream/answer/{0}/{1}'.format(r_token,r_hash),
                          data=json.dumps("invalid proof object"),
                          content_type='application/json')
        self.assertEqual(r.status_code,500)

        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['message'],'Posted data must be an JSON encoded \
proof object: {"proof":"...proof object..."}')


class TestDownstreamNodeFuncs(unittest.TestCase):
    def setUp(self):
        db.create_all()
        self.testfile = RandomIO().genfile(1000)
            
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
        
        # test random address
        with self.assertRaises(RuntimeError) as ex:
            db_token = node.create_token('randomaddress')
        
        self.assertEqual(str(ex.exception),'Invalid address given.')

    def test_delete_token(self):
        db_token = node.create_token(self.test_address)
        
        t = db_token.token
        
        node.delete_token(db_token.token)
        
        db_token = models.Token.query.filter(models.Token.token==t).first()
        
        self.assertIsNone(db_token)
        
        with self.assertRaises(RuntimeError) as ex:
            node.delete_token('nonexistent token')
            
        self.assertEqual(str(ex.exception),'Invalid token given. Token does not exist.')

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
            db_token = node.create_token(self.test_address)
            
            beat = pickle.loads(db_token.heartbeat)
            
            with open(db_file.path,'rb') as f:
                (tag,state) = beat.encode(f)
                
            chal = beat.gen_challenge(state)
            
            contract = models.Contract(token_id = db_token.id,
                                       file_id = db_file.id,
                                       state = pickle.dumps(state),
                                       challenge = pickle.dumps(chal),
                                       expiration = datetime.utcnow() + timedelta(seconds = db_file.interval))
                                 
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
        with self.assertRaises(RuntimeError) as ex:
            node.remove_file('nonexsistant hash')
            
        self.assertEqual(str(ex.exception),'File does not exist.  Cannot remove non existant file')
        
    def test_get_chunk_contract(self):
        db_token = node.create_token(self.test_address)
        
        db_contract = node.get_chunk_contract(db_token.token)
        
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
        
        with self.assertRaises(RuntimeError) as ex:
            node.get_chunk_contract('nonexistent token')
        
        self.assertEqual(str(ex.exception),'Invalid token given.')
        
    def test_verify_proof(self):
        db_token = node.create_token(self.test_address)
        
        db_contract = node.get_chunk_contract(db_token.token)
        
        beat = pickle.loads(db_token.heartbeat)
        
        # get tags
        with open(db_contract.tag_path,'rb') as f:
            tag = pickle.load(f)
        
        chal = pickle.loads(db_contract.challenge)
        
        # generate a proof
        with open(db_contract.file.path,'rb') as f:
            proof = beat.prove(f,chal,tag)
            
        self.assertTrue(node.verify_proof(db_token.token,db_contract.file.hash,proof))

        # check nonexistent token
        
        with self.assertRaises(RuntimeError) as ex:
            node.verify_proof('invalid token',db_contract.file.hash,proof)
            
        self.assertEqual(str(ex.exception),'Invalid token')
        
        os.remove(db_contract.file.path)
        os.remove(db_contract.tag_path)
        
        # check nonexistent file
        
        with self.assertRaises(RuntimeError) as ex:
            node.verify_proof(db_token.token,'invalid file hash',proof)
            
        self.assertEqual(str(ex.exception),'Invalid file hash')
        
        db_token = node.create_token(self.test_address)
        
        # check nonexistent contract
        
        db_file = node.add_file(self.testfile)
        
        with self.assertRaises(RuntimeError) as ex:
            node.verify_proof(db_token.token,db_file.hash,proof)
            
        self.assertEqual(str(ex.exception),'Contract does not exist.')
        
        # check expiration
        db_token = node.create_token(self.test_address)
            
        beat = pickle.loads(db_token.heartbeat)
        
        with open(db_file.path,'rb') as f:
            (tag,state) = beat.encode(f)
            
        chal = beat.gen_challenge(state)
        
        db_contract = models.Contract(token_id = db_token.id,
                                      file_id = db_file.id,
                                      state = pickle.dumps(state),
                                      challenge = pickle.dumps(chal),
                                      expiration = datetime.utcnow()-timedelta(seconds=1))
                             
        db.session.add(db_contract)
        db.session.commit()
        
        with open(db_contract.file.path,'rb') as f:
            proof = beat.prove(f,chal,tag)
        
        self.assertFalse(node.verify_proof(db_token.token,db_contract.file.hash,proof))
        
        node.remove_file(db_file.hash)


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