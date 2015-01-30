#!/usr/bin/env python
# -*- coding: utf-8 -*-
from sqlalchemy import and_, func, text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import false
from datetime import datetime, timedelta

from .startup import db
from .uptime import UptimeSummary, UptimeCalculator
from .types import MutableTypeWrapper


class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    path = db.Column(db.String(128), unique=True)
    redundancy = db.Column(db.Integer(), nullable=False)
    interval = db.Column(db.Integer(), nullable=False)
    added = db.Column(db.DateTime(), nullable=False)
    # for prototyping we will have file seed and size here
    seed = db.Column(db.String(128))
    size = db.Column(db.Integer())


class Address(db.Model):
    __tablename__ = 'addresses'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    address = db.Column(
        db.String(128), nullable=False, unique=True, index=True)
    crowdsale_balance = db.Column(db.BigInteger(), nullable=True)

    __table_args__ = (
        db.Index('ix_addresses_address_crowdsale_balance',
                 'address',
                 'crowdsale_balance'), )


class Token(db.Model):
    __tablename__ = 'tokens'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    token = db.Column(db.String(32), nullable=False, unique=True, index=True)
    address_id = db.Column(db.ForeignKey('addresses.id'))
    # moving to an app wide heartbeat
    # heartbeat = db.Column(db.PickleType(), nullable=False)
    ip_address = db.Column(db.String(32), nullable=False, index=True)
    farmer_id = db.Column(db.String(20), nullable=False, unique=True)
    hbcount = db.Column(db.Integer(), nullable=False, default=0)
    location = db.Column(db.PickleType())
    # shouldn't need unicode, since it will have come over JSON which will have
    # escaped any unicode characters.  need to test that behavior.
    message = db.Column(db.Text())
    signature = db.Column(db.Text())

    # uptime summary
    start = db.Column(db.DateTime())
    end = db.Column(db.DateTime())
    upsum = db.Column(
        db.Interval(), nullable=False, default=timedelta(seconds=0))

    address = db.relationship('Address',
                              backref=db.backref('tokens',
                                                 lazy='dynamic',
                                                 cascade='all, delete-orphan'))

    @hybrid_property
    def online(self):
        return any(c.expiration > datetime.utcnow() for c in self.contracts)

    # @online.expression
    # def online(self):
    #     return exists().where(and_(Contract.expiration > datetime.utcnow(),
    #                                Contract.token_id == self.id)).\
    #         label('online')

    @property
    def uptime(self):
        if (self.start is None):
            first_contract = Contract.query.filter(Contract.token_id == self.id).\
                order_by(Contract.start).first()

            if (first_contract is not None):
                self.start = first_contract.start

        uncached = Contract.query.filter(and_(Contract.token_id == self.id,
                                              Contract.cached == false())).\
            all()

        calc = UptimeCalculator(
            uncached, UptimeSummary(self.start, self.end, self.upsum))

        summary = calc.update()

        self.start = summary.start
        self.end = summary.end
        self.upsum = summary.uptime

        return summary.fraction()

    # Return the date of the contract with the latest due date.
    @property
    def last_due(self):
        contracts = Contract.query.filter(Contract.token_id == self.id).all()
        sorted_dates = sorted([c.due for c in contracts])
        num_dates = len(sorted_dates)
        return sorted_dates.pop().isoformat() if num_dates > 0 else None

    @hybrid_property
    def contract_count(self):
        return self.contracts.count()

    # @contract_count.expression
    # def contract_count(self):
    #     return select([func.count()]).where(Contract.token_id == self.id).\
    #         label('contract_count')

    @hybrid_property
    def size(self):
        return sum(c.file.size for c in self.contracts)

    # deprecated
    # @size.expression
    #  def size(self):
    #     return select([func.sum(Contract.size)]).\
    #         where(Contract.token_id == self.id).label('size')

    @hybrid_property
    def addr(self):
        return self.address.address

    # @addr.expression
    # def addr(self):
    #     return select([Address.address]).\
    #         where(Address.id == self.address_id).\
    #         label('addr')


class Chunk(db.Model):

    """For storing cached chunks before they are distributed to farmers.
    A script will maintain a certain number of chunks in this database so that
    new farmers can quickly obtain test chunks
    """
    __tablename__ = 'chunks'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    file_id = db.Column(db.ForeignKey('files.id'))
    state = db.Column(db.PickleType(), nullable=False)
    tag_path = db.Column(db.String(128), unique=True)

    file = db.relationship('File',
                           backref=db.backref('chunks',
                                              lazy='dynamic',
                                              cascade='all, delete-orphan'))


class Contract(db.Model):
    __tablename__ = 'contracts'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    token_id = db.Column(db.ForeignKey('tokens.id'), index=True)
    file_id = db.Column(db.ForeignKey('files.id'))
    state = db.Column(
        MutableTypeWrapper.as_mutable(db.PickleType), nullable=False)
    challenge = db.Column(db.PickleType())
    tag_path = db.Column(db.String(128), unique=True)
    start = db.Column(db.DateTime())
    due = db.Column(db.DateTime())
    answered = db.Column(db.Boolean(), default=False)
    cached = db.Column(db.Boolean(), default=False, index=True)

    token = db.relationship('Token',
                            backref=db.backref('contracts',
                                               lazy='dynamic',
                                               cascade='all, delete-orphan'))

    file = db.relationship('File',
                           backref=db.backref('contracts',
                                              lazy='dynamic',
                                              cascade='all, delete-orphan'))

    __table_args__ = (
        db.Index('ix_contracts_token_id_file_id', 'token_id', 'file_id'),
        db.Index('ix_contracts_token_id_cached', 'token_id', 'cached'))

    @hybrid_property
    def expiration(self):
        if (self.answered):
            return self.due + timedelta(seconds=self.file.interval)
        else:
            return self.due

    @expiration.expression
    def expiration(cls):
        # MySQL specific code.  will need to check compatibility on
        # moving to different db
        return func.IF(cls.__table__.c.answered,
                       func.TIMESTAMPADD(text('SECOND'),
                                         File.__table__.c.interval,
                                         cls.__table__.c.due),
                       cls.__table__.c.due)
