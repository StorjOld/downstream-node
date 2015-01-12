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


def load_heartbeat(constructor, path):
    # we shall save the app wide heartbeat into a binary file
    if (os.path.isfile(path)):
        with open(path, 'rb') as f:
            return pickle.load(f)
    else:
        beat = constructor()
        with open(path, 'wb') as f:
            pickle.dump(beat, f)
        return beat


app.heartbeat = load_heartbeat(
    app.config['HEARTBEAT'], app.config['HEARTBEAT_PATH'])


if (app.config['MONGO_LOGGING']):
    app.mongo_logger = mongolog(app.config['MONGO_URI'],
                                app.config['SERVER_ALIAS'])
else:
    app.mongo_logger = None

from . import routes  # NOQA
# from . import profiling
