#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import heartbeat

# Flask
DEBUG = False
SECRET_KEY = os.urandom(32)
APPLICATION_ROOT = '/api/downstream/v1'
SERVER_ALIAS = 'dsnode'

# SQLAlchemy (DB)
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://localhost/downstream'  # NOQA

FILES_PATH = 'tmp/'
TAGS_PATH = 'tags/'
MMDB_PATH = 'data/GeoLite2-City.mmdb'

# the heartbeat we use should probably eventually be associated with
# the uploading user so they can decide on the check_fraction...
HEARTBEAT = heartbeat.Merkle.Merkle
HEARTBEAT_PATH = 'data/heartbeat'

MONGO_LOGGING = True
MONGO_URI = 'mongodb://localhost/dsnode_log'
PROFILE = False

DEFAULT_CHUNK_SIZE = 33554432
MAX_TOKENS_PER_IP = 5
MIN_SJCX_BALANCE = 10000
MAX_SIG_MESSAGE_SIZE = 1024
REQUIRE_SIGNATURE = True
