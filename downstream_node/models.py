#!/usr/bin/env python
# -*- coding: utf-8 -*-
from .startup import db
from sqlalchemy import select, func, and_, Float, text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import exists
from sqlalchemy.sql.expression import cast
from datetime import datetime, timedelta


class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    hash = db.Column(db.String(128), nullable=False, unique=True)
    path = db.Column(db.String(128), unique=True)
    redundancy = db.Column(db.Integer(), nullable=False)
    interval = db.Column(db.Integer(), nullable=False)
    added = db.Column(db.DateTime(), nullable=False)


class Address(db.Model):
    __tablename__ = 'addresses'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    address = db.Column(db.String(128), nullable=False, unique=True)
    crowdsale_balance = db.Column(db.BigInteger(), nullable=True)


class Token(db.Model):
    __tablename__ = 'tokens'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    token = db.Column(db.String(32), nullable=False, unique=True)
    address_id = db.Column(db.ForeignKey('addresses.id'))
    heartbeat = db.Column(db.LargeBinary(), nullable=False)
    ip_address = db.Column(db.String(32), nullable=False, unique=True)
    farmer_id = db.Column(db.String(20), nullable=False, unique=True)
    hbcount = db.Column(db.Integer(), nullable=False, default=0)
    location = db.Column(db.LargeBinary())

    address = db.relationship('Address',
                              backref=db.backref('tokens',
                                                 lazy='dynamic',
                                                 cascade='all, delete-orphan'))

    @hybrid_property
    def online(self):
        return any(c.expiration > datetime.utcnow() for c in self.contracts)

    @online.expression
    def online(self):
        return exists().where(and_(Contract.expiration > datetime.utcnow(),
                                   Contract.token_id == self.id)).\
            label('online')

    @hybrid_property
    def uptime(self):
        # we want the sum of the uptimes of all the contracts divided
        # by the sum of the total time of all the contracts
        uptime = sum(c.uptime.total_seconds() for c in self.contracts)
        total = sum(c.totaltime.total_seconds() for c in self.contracts)
        return float(uptime) / float(total) if total > 0 else 0

    @uptime.expression
    def uptime(self):
        return select([func.IF(Contract.totaltime > 0,
                               cast(func.sum(Contract.uptime), Float) /
                               cast(func.sum(Contract.totaltime), Float),
                               0)]).\
            where(Contract.token_id == self.id).label('uptime')

    @hybrid_property
    def contract_count(self):
        return self.contracts.count()

    @contract_count.expression
    def contract_count(self):
        return select([func.count()]).where(Contract.token_id == self.id).\
            label('contract_count')

    @hybrid_property
    def size(self):
        return sum(c.size for c in self.contracts)

    @size.expression
    def size(self):
        return select([func.sum(Contract.size)]).\
            where(Contract.token_id == self.id).label('size')

    @hybrid_property
    def addr(self):
        return self.address.address

    @addr.expression
    def addr(self):
        return select([Address.address]).where(Address.id == self.address_id).\
            label('addr')


class Contract(db.Model):
    __tablename__ = 'contracts'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    token_id = db.Column(db.ForeignKey('tokens.id'))
    file_id = db.Column(db.ForeignKey('files.id'))
    state = db.Column(db.LargeBinary(), nullable=False)
    challenge = db.Column(db.LargeBinary())
    tag_path = db.Column(db.String(128), unique=True)
    start = db.Column(db.DateTime())
    due = db.Column(db.DateTime())
    answered = db.Column(db.Boolean(), default=False)
    # for prototyping, include file seed for regeneration, and file size
    seed = db.Column(db.String(128))
    size = db.Column(db.Integer())

    token = db.relationship('Token',
                            backref=db.backref('contracts',
                                               lazy='dynamic',
                                               cascade='all, delete-orphan'))

    file = db.relationship('File',
                           backref=db.backref('contracts',
                                              lazy='dynamic',
                                              cascade='all, delete-orphan'))

    @hybrid_property
    def expiration(self):
        if (self.answered):
            return self.due + timedelta(seconds=self.file.interval)
        else:
            return self.due

    @expiration.expression
    def expiration(self):
        # MySQL specific code.  will need to check compatibility on
        # moving to different db
        return select([func.IF(self.answered,
                               func.TIMESTAMPADD(text('SECOND'),
                                                 File.interval,
                                                 self.due),
                               self.due)]).\
            where(File.id == self.file_id).label('expiration')

    @hybrid_property
    def uptime(self):
        # returns uptime as a timedelta
        # if expiration > now, then this is (now-start)
        # otherwise it is (expiration-start)
        now = datetime.utcnow()
        if self.expiration > now:
            return now-self.start
        else:
            return self.expiration-self.start

    @uptime.expression
    def uptime(self):
        # this code is MySQL specific.  if we switch to another database
        # we will need to port this to another language, possibly.
        now = datetime.utcnow()
        return func.IF(self.expiration > now,
                       func.TIMESTAMPDIFF(text('SECOND'),
                                          self.start,
                                          now),
                       func.TIMESTAMPDIFF(text('SECOND'),
                                          self.start,
                                          self.expiration)).\
            label('uptime')

    @hybrid_property
    def totaltime(self):
        return datetime.utcnow() - self.start

    @totaltime.expression
    def totaltime(self):
        return func.TIMESTAMPDIFF(text('SECOND'),
                                  self.start,
                                  datetime.utcnow()).label('totaltime')
