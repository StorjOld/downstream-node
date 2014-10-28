#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import heartbeat

# Flask
SECRET_KEY = os.urandom(32)

# SQLAlchemy (DB)
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://localhost/downstream'  # NOQA

FILES_PATH = 'tmp/'
TAGS_PATH = 'tags/'
MMDB_PATH = 'data/GeoLite2-City.mmdb'

TEST_FILE_SIZE = 100

HEARTBEAT = heartbeat.Swizzle.Swizzle

ONE_TOKEN_PER_IP = True
REQUIRE_SIGNATURE = True
MIN_SJCX_BALANCE = 10000
