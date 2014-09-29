#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .startup import db


class Files(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    name = db.Column(db.String(128), unique=True)


class Challenges(db.Model):
    __tablename__ = 'challenges'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    filename = db.Column(db.ForeignKey('files.name'))
    rootseed = db.Column(db.String(128), nullable=False)
    block = db.Column(db.Integer(), nullable=False)
    seed = db.Column(db.String(128), nullable=False)
    response = db.Column(db.String(128))

class Addresses(db.Model):
    __tablename__ = 'addresses'
    
    address = db.Column(db.String(128),primary_key=True)
    
class Tokens(db.Model):
    __tablename__ = 'tokens'
    
    token = db.Column(db.String(32), primary_key=True, nullable=False)
    address = db.Column(db.ForeignKey('addresses.address'))
    heartbeat = db.Column(db.LargeBinary(), nullable=False)