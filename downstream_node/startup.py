#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

from . import config
from .log import mongolog

app = Flask(__name__)
app.config.from_object(config)
db = SQLAlchemy(app)
app.heartbeat = app.config['HEARTBEAT']()
if (app.config['MONGO_LOGGING']):
    app.mongo_logger = mongolog(app.config['MONGO_URI'])
else:
    app.mongo_logger = None

from . import routes  # NOQA
