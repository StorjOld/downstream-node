#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from heartbeat import SwPriv

# Flask
SECRET_KEY = os.urandom(32)

# SQLAlchemy (DB)
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://localhost/downstream'  # NOQA

FILES_PATH = 'tmp/'
TAGS_PATH = 'tags/'

TEST_FILE_SIZE = 100

HEARTBEAT = SwPriv.SwPriv
