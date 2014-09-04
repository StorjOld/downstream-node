#!/usr/bin/env python
# -*- coding: utf-8 -*-
from downstream_node.startup import db


class Files(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    filepath = db.Column('filepath', db.String())


class Challenges(db.Model):
    __tablename__ = 'challenges'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    filepath = db.Column(db.ForeignKey('files.filepath'))
    block = db.Column('block', db.String())
    seed = db.Column('seed', db.String())
    response = db.Column('response', db.String(), nullable=True)
