#!/usr/bin/env python
# -*- coding: utf-8 -*-
from downstream_node.startup import db


class Files(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column(db.String(512), unique=True)


class Challenges(db.Model):
    __tablename__ = 'challenges'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    filename = db.Column(db.ForeignKey('files.name'))
    rootseed = db.Column(db.String(128), nullable=False)
    block = db.Column(db.String(128), nullable=False)
    seed = db.Column(db.String(128), nullable=False)
    response = db.Column(db.String(128))
