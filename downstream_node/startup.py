#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import pickle
import requests

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

from . import config
from .log import mongolog

app = Flask(__name__)
app.config.from_object(config)
db = SQLAlchemy(app)

def try_local_heartbeat(path):
    if (os.path.isfile(path)):
        with open(path, 'rb') as f:
            return pickle.load(f)
    else:
        return False

def try_remote_heartbeat(path):
    try:
        response = requests.get(path)
        response.raise_for_status()
        return pickle.loads(response.content)
    except:
        return False

        
def load_heartbeat(constructor, path, check_fraction):
    # we shall save the app wide heartbeat into a binary file
    beat = try_local_heartbeat(path)
    
    if (not beat):
        beat = try_remote_heartbeat(path)
    
    if (not beat):
        beat = constructor(check_fraction)
        with open(path, 'wb') as f:
            pickle.dump(beat, f)
    
    return beat


def load_logger(log, uri, server_alias):
    if (log):
        return mongolog(uri, server_alias)
    else:
        return None

app.heartbeat = load_heartbeat(
    app.config['HEARTBEAT'],
    app.config['HEARTBEAT_PATH'],
    app.config['HEARTBEAT_CHECK_FRACTION'])

app.mongo_logger = load_logger(app.config['MONGO_LOGGING'],
                               app.config['MONGO_URI'],
                               app.config['SERVER_ALIAS'])


from . import routes  # NOQA

if (app.config['PROFILE']):
    from . import profiling  # NOQA
