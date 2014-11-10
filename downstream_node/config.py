#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import heartbeat

# Flask
SECRET_KEY = os.urandom(32)
APPLICATION_ROOT = '/api/downstream/v1'

# SQLAlchemy (DB)
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://localhost/downstream'  # NOQA

FILES_PATH = 'tmp/'
TAGS_PATH = 'tags/'
MMDB_PATH = 'data/GeoLite2-City.mmdb'

TEST_FILE_SIZE = 100

HEARTBEAT = heartbeat.Swizzle.Swizzle

MAX_TOKENS_PER_IP = 5
MIN_SJCX_BALANCE = 10000
REQUIRE_SIGNATURE = True  # not used yet
