import unittest
import mock
import json

from mock import Mock, patch


from downstream_node.startup import app, db, load_heartbeat, load_logger
from downstream_node import models
from downstream_node import node
from downstream_node import config
from downstream_node import uptime
from downstream_node import log


# new testing methodology.
# we'll test each route.  we'll set up the database for the preconditions
# and then ensure that the returned data is correct for the given input
# tests will be grouped by database set up

class TestDownstreamNodeRoutes(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        app.config['TESTING'] = True
        app.config['REQUIRE_SIGNATURE'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://localhost/test_downstream'
        db.engine.execute('DROP TABLE IF EXISTS contracts,chunks,tokens,addresses,files')
        db.create_all()
        
    def tearDown(self):
        db.session.close()
        db.engine.execute('DROP TABLE IF EXISTS contracts,chunks,tokens,addresses,files')
        
class TestApiIndex(TestDownstreamNodeRoutes):
    def test_index(self):
        r = self.app.get('/')
        
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content_type, 'application/json')
        
        r_json = json.loads(r.data.decode('utf-8'))
        
        self.assertEqual(r_json['msg'],'ok')
        
class TestStatusList(TestDownstreamNodeRoutes):
    def setUp(self):
        TestDownstreamNodeRoutes.setUp(self)
        
    def tearDown(self):
        TestDownstreamNodeRoutes.tearDown(self)