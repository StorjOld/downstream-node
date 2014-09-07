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
    root_seed = db.Column(db.String())
    block = db.Column(db.String())
    seed = db.Column(db.String())
    response = db.Column(db.String(), nullable=True)
