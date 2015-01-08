#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import pickle

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

from . import config
from .log import mongolog

app = Flask(__name__)
app.config.from_object(config)
db = SQLAlchemy(app)

# we shall save the app wide heartbeat into a binary file
if (os.path.isfile(app.config['HEARTBEAT_PATH'])):
    with open(app.config['HEARTBEAT_PATH'], 'rb') as f:
        app.heartbeat = pickle.load(f)
else:
    app.heartbeat = app.config['HEARTBEAT']()
    with open(app.config['HEARTBEAT_PATH'], 'wb') as f:
        pickle.dump(app.heartbeat, f)

if (app.config['MONGO_LOGGING']):
    app.mongo_logger = mongolog(app.config['MONGO_URI'],
                                app.config['SERVER_ALIAS'])
else:
    app.mongo_logger = None

from . import routes  # NOQA
# from . import profiling
