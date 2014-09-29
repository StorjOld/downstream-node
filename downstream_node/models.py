#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .startup import db


class Files(db.Model):
    __tablename__ = 'files'

    hash = db.Column(db.String(128), primary_key=True, unique=True)
    path = db.Column(db.String(128), unique=True)
    redundancy = db.Column(db.Integer(), nullable=False)
    interval = db.Column(db.Integer(), nullable=False)
    added = db.Column(db.DateTime(), nullable=False)


class Addresses(db.Model):
    __tablename__ = 'addresses'

    address = db.Column(db.String(128), primary_key=True)


class Tokens(db.Model):
    __tablename__ = 'tokens'

    token = db.Column(db.String(32), primary_key=True, nullable=False)
    address = db.Column(db.ForeignKey('addresses.address'))
    heartbeat = db.Column(db.LargeBinary(), nullable=False)


class Contracts(db.Model):
    __tablename__ = 'contracts'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    token = db.Column(db.ForeignKey('tokens.token'))
    file = db.Column(db.ForeignKey('files.hash'))
    state = db.Column(db.LargeBinary(), nullable=False)
    challenge = db.Column(db.LargeBinary(), nullable=False)
    expiration = db.Column(db.DateTime(), nullable=False)
