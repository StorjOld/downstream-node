#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

from . import config

app = Flask(__name__)
app.config.from_object(config)
db = SQLAlchemy(app)
app.heartbeat = app.config['HEARTBEAT']()

from . import routes  # NOQA
