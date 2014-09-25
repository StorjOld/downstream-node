#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

# Flask
SECRET_KEY = os.urandom(32)

# SQLAlchemy (DB)
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://downstream:password@localhost/downstream'  # NOQA

# Heartbeat
HEARTBEAT_SECRET = (
    r'6\x1eg\xd4\x19\xde\xad\xc1x\x00+\xc9\x04~_`%\x'
    r'f0\x7fF\xd9\x0b=\x91J\xe5\x0b\xeb\xc1D\xcd\x8d'
)

FILES_PATH = 'tmp'
