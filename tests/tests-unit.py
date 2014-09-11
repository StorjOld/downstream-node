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
        r = self.app.get('api/downstream/challenges/answer/test')



if __name__ == '__main__':
    unittest.main()