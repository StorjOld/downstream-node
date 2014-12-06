#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import heartbeat

# Flask
DEBUG = True
SECRET_KEY = os.urandom(32)
APPLICATION_ROOT = '/api/downstream/v1'
SERVER_ALIAS = 'dsnode'

# SQLAlchemy (DB)
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://localhost/downstream'  # NOQA

FILES_PATH = 'tmp/'
TAGS_PATH = 'tags/'
MMDB_PATH = 'data/GeoLite2-City.mmdb'


HEARTBEAT = heartbeat.Swizzle.Swizzle

MONGO_LOGGING = False
MONGO_URI = 'mongodb://localhost/dsnode_log'

MAX_CHUNK_SIZE = 3200
DEFAULT_CHUNK_SIZE = 100
MAX_TOKENS_PER_IP = 5
MIN_SJCX_BALANCE = 10000
MAX_SIG_MESSAGE_SIZE = 1024
REQUIRE_SIGNATURE = False
