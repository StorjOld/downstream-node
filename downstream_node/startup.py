#!/usr/bin/env python
# -*- coding: utf-8 -*-

from . import app, db
from .config import config

app.config.from_object(config)

db.init_app(app)
