#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os

import unittest

from heartbeat import Heartbeat

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
        db.engine.execute('DROP TABLE challenges,files')
        os.remove(self.testfile)
        del self.app

    def test_api_downstream_challenge(self):
        r = self.app.get('/api/downstream/challenges/test.file')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data.decode('utf-8'))
        self.assertIsInstance(r_json, dict)
        self.assertEqual(len(r_json.get('challenges')), 1000)
        self.assertEqual(r_json.get('challenges')[0].get('filename'), 'test.file')

    def test_api_downstream_challenge_answer(self):
        # Prime DB
        self.app.get('/api/downstream/challenges/test.file')

        r = self.app.get('/api/downstream/challenges/answer/test.file')
        self.assertEqual(r.status_code, 405)

        r = self.app.post('/api/downstream/challenges/answer/test.file')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data.decode('utf-8')).get('msg'), 'missing request json')

        data = {
            'seed': 'test seed'
        }
        r = self.app.post(
            '/api/downstream/challenges/answer/test.file',
            data=json.dumps(data)
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data.decode('utf-8')).get('msg'), 'missing data')

        data.update({
            'response': 'test response',
            'block': 12345
        })
        r = self.app.post(
            '/api/downstream/challenges/answer/test.file',
            data=json.dumps(data)
        )
        self.assertEqual(r.status_code, 404)

        chals = models.Challenges(
            filename='test.file',
            rootseed='test root seed',
            seed='test seed',
            block=12345,
            response='test response'
        )
        db.session.add(chals)
        db.session.commit()

        r = self.app.post(
            '/api/downstream/challenges/answer/test.file',
            data=json.dumps(data)
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.data.decode('utf-8')).get('msg'), 'ok')
        self.assertIs(json.loads(r.data.decode('utf-8')).get('match'), True)


class TestDownstreamModels(unittest.TestCase):
    def test_files(self):
        self.assertEqual(getattr(models.Files, '__tablename__'), 'files')
        self.assertTrue(hasattr(models.Files, 'id'))
        self.assertTrue(hasattr(models.Files, 'name'))

    def test_challenges(self):
        self.assertEqual(getattr(models.Challenges, '__tablename__'), 'challenges')
        self.assertTrue(hasattr(models.Challenges, 'id'))
        self.assertTrue(hasattr(models.Challenges, 'filename'))
        self.assertTrue(hasattr(models.Challenges, 'rootseed'))
        self.assertTrue(hasattr(models.Challenges, 'block'))
        self.assertTrue(hasattr(models.Challenges, 'seed'))
        self.assertTrue(hasattr(models.Challenges, 'response'))


class TestDownstreamNodeFuncs(unittest.TestCase):
    def setUp(self):
        self.testfile = os.path.abspath('tests/test.file')
        with open(self.testfile,'wb+') as f:
            f.write(os.urandom(1000))

    def tearDown(self):
        os.remove(self.testfile)
        pass

    def test_create_token(self):
        with self.assertRaises(NotImplementedError):
            node.create_token()

    def test_delete_token(self):
        with self.assertRaises(NotImplementedError):
            node.delete_token()

    def test_add_file(self):
        with self.assertRaises(NotImplementedError):
            node.add_file()

    def test_remove_file(self):
        with self.assertRaises(NotImplementedError):
            node.remove_file()

    def test_gen_challenges(self):
        db.create_all()
        node.gen_challenges(self.testfile, 'test root seed')
        challenges = models.Challenges.query.all()
        db.session.close()
        db.engine.execute('DROP TABLE challenges,files')
        self.assertEqual(len(challenges), 1000)

    def test_update_challenges(self):
        with self.assertRaises(NotImplementedError):
            node.update_challenges()


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
        os.remove(self.testfile)
        db.session.close()
        db.engine.execute('DROP TABLE challenges,files')
        del self.app

    def test_query_to_list(self):
        node.gen_challenges(self.testfile, 'test root seed')
        result = utils.query_to_list(models.Challenges.query)
        self.assertIsInstance(result, list)
        [self.assertIsInstance(item, dict) for item in result]

    def test_load_heartbeat(self):
        test_hb = Heartbeat(self.testfile, 'test secret')
        node.gen_challenges(self.testfile, 'test root seed')
        result = models.Challenges.query.all()
        hb = utils.load_heartbeat(test_hb, result)
        self.assertEqual(len(hb.challenges), 1000)


if __name__ == '__main__':
    unittest.main()