#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

import unittest

from downstream_node.startup import app, db
from downstream_node.models import Challenges


class TestDownstream(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        db.create_all()

    def tearDown(self):
        db.engine.execute('DROP TABLE challenges,files')
        del self.app

    def test_api_downstream_challenge(self):
        r = self.app.get('/api/downstream/challenges/test')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')

        r_json = json.loads(r.data)
        self.assertIsInstance(r_json, dict)
        self.assertEqual(len(r_json.get('challenges')), 1000)
        self.assertEqual(r_json.get('challenges')[0].get('filename'), 'thirty-two_meg.testfile')

    def test_api_downstream_challenge_answer(self):
        # Prime DB
        self.app.get('/api/downstream/challenges/test')

        r = self.app.get('/api/downstream/challenges/answer/test')
        self.assertEqual(r.status_code, 405)

        r = self.app.post('/api/downstream/challenges/answer/test')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data).get('msg'), 'missing request json')

        data = {
            'seed': 'test seed'
        }
        r = self.app.post(
            '/api/downstream/challenges/answer/test',
            data=json.dumps(data)
        )
        self.assertEqual(r.status_code, 400)
        self.assertEqual(json.loads(r.data).get('msg'), 'missing data')

        data.update({
            'response': 'test response',
            'block': 12345
        })
        r = self.app.post(
            '/api/downstream/challenges/answer/test',
            data=json.dumps(data)
        )
        self.assertEqual(r.status_code, 404)

        chals = Challenges(
            filename='thirty-two_meg.testfile',
            rootseed='test root seed',
            seed='test seed',
            block=12345,
            response='test response'
        )
        db.session.add(chals)
        db.session.commit()

        r = self.app.post(
            '/api/downstream/challenges/answer/test',
            data=json.dumps(data)
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(json.loads(r.data).get('msg'), 'ok')
        self.assertIs(json.loads(r.data).get('match'), True)


if __name__ == '__main__':
    unittest.main()