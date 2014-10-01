#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .startup import db


class File(db.Model):
    __tablename__ = 'files'

    hash = db.Column(db.String(128), primary_key=True)
    path = db.Column(db.String(128), unique=True)
    redundancy = db.Column(db.Integer(), nullable=False)
    interval = db.Column(db.Integer(), nullable=False)
    added = db.Column(db.DateTime(), nullable=False)


class Address(db.Model):
    __tablename__ = 'addresses'

    address = db.Column(db.String(128), primary_key=True)


class Token(db.Model):
    __tablename__ = 'tokens'

    token = db.Column(db.String(32), primary_key=True)
    address = db.Column(db.ForeignKey('addresses.address'))
    heartbeat = db.Column(db.LargeBinary(), nullable=False)


class Contract(db.Model):
    __tablename__ = 'contracts'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    token = db.Column(db.ForeignKey('tokens.token'))
    file_hash = db.Column(db.ForeignKey('files.hash'))
    state = db.Column(db.LargeBinary(), nullable=False)
    challenge = db.Column(db.LargeBinary(), nullable=False)
    expiration = db.Column(db.DateTime(), nullable=False)
    # for prototyping, include file seed for regeneration
    seed = db.Column(db.String(128))

    file = db.relationship('File',
                           backref=db.backref('contracts',
                                              lazy='dynamic',
                                              cascade='all, delete-orphan'))
