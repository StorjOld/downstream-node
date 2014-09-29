#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os
import pickle

import unittest

from heartbeat import Heartbeat, heartbeat_type

from downstream_node.startup import app, db
from downstream_node import models
from downstream_node.lib import node, utils
from downstream_node.config import config


class TestDownstreamRoutes(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        db.create_all()
        self.testfile = os.path.abspath(os.path.join(config.FILES_PATH,'test.file'))
        with open(self.testfile,'wb+') as f:
            f.write(os.urandom(1000))

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE tokens,challenges,addresses,files')
        os.remove(self.testfile)
        del self.app

    def test_api_downstream_new(self):
        test_address = '13FfNS1wu6u7G9ZYQnyxYP1YRntEqAyEJJ'
        address = models.Addresses(address=test_address)
        db.session.add(address)
        db.session.commit()
        
        r = self.app.get('/api/downstream/new/{0}'.format(test_address))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        r_token = r_json['token']
        
        r_beat = heartbeat_type().fromdict(r_json['heartbeat'])
        
        token = models.Tokens.query.filter(models.Tokens.token==r_token).first()
        
        self.assertEqual(token.token,r_token)
        self.assertEqual(pickle.loads(token.heartbeat),r_beat)


class TestDownstreamNodeFuncs(unittest.TestCase):
    def setUp(self):
        db.create_all()
        self.testfile = os.path.abspath('tests/test.file')
        with open(self.testfile,'wb+') as f:
            f.write(os.urandom(1000))
            
        self.test_address = '13FfNS1wu6u7G9ZYQnyxYP1YRntEqAyEJJ'
        
        address = models.Addresses(address=self.test_address)
        db.session.add(address)
        db.session.commit()

    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE tokens,challenges,addresses,files')
        os.remove(self.testfile)
        pass

    def test_create_token(self):
        (token,beat) = node.create_token(self.test_address)
        
        # verify that the info is in the database
        token = models.Tokens.query.filter(models.Tokens.token==token).first()
        
        dbbeat = pickle.loads(token.heartbeat)
        
        self.assertEqual(beat,dbbeat)

    def test_delete_token(self):
        (t,beat) = node.create_token(self.test_address)
    
        token = models.Tokens.query.filter(models.Tokens.token==t).first()
        
        node.delete_token(token.token)
        
        token = models.Tokens.query.filter(models.Tokens.token==t).first()
        
        self.assertIsNone(token)

    def test_add_file(self):
        with self.assertRaises(NotImplementedError):
            node.add_file()

    def test_remove_file(self):
        with self.assertRaises(NotImplementedError):
            node.remove_file()


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
        db.engine.execute('DROP TABLE tokens,challenges,addresses,files')
        os.remove(self.testfile)
        del self.app


if __name__ == '__main__':
    unittest.main()