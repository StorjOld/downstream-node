#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import heartbeat

# Flask
SECRET_KEY = os.urandom(32)

# SQLAlchemy (DB)
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://downstream:RR6WZXK9JrGhdtoqmRCSnF84RRiHn8PmkLAHNtucBvI@localhost/downstream'  # NOQA

FILES_PATH = '/var/tmp/'
TAGS_PATH = '/var/tmp/'

TEST_FILE_SIZE = 100

HEARTBEAT = heartbeat.SwPriv.SwPriv
