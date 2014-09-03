#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

__version__ = '0.1dev'

app = Flask(__name__)
db = SQLAlchemy()

import startup
