#!/usr/bin/env python
# -*- coding: utf-8 -*-
from sqlalchemy import func, text, Float, bindparam
from sqlalchemy.sql import select
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import false, true
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

    @online.expression
    def online(self):
        return func.IF(func.sum(Contract.online) > 0, true(), false())

    @hybrid_property
    def online_time(self):
        return self.upsum.total_seconds()

    @hybrid_property
    def total_time(self):
        return (self.end - self.start).total_seconds()

    @hybrid_property
    def fraction(self):
        return float(self.online_time) / \
            float((self.total_time).total_seconds())

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

    @hybrid_property
    def size(self):
        return sum(c.file.size for c in self.contracts)

    @hybrid_property
    def addr(self):
        return self.address.address

    @total_time.expression
    def total_time(cls):
        return func.TIMESTAMPDIFF(text('second'),
                                  cls.__table__.c.start,
                                  cls.__table__.c.end)

    @online_time.expression
    def online_time(cls):
        return func.TIMESTAMPDIFF(text('second'),
                                  '1970-01-01',
                                  cls.__table__.c.upsum)

    @fraction.expression
    def fraction(cls):
        return func.IF(func.ABS(cls.total_time) > 0,
                       func.cast(cls.online_time, Float) /
                       func.cast(cls.total_time, Float), 0)

    @hybrid_property
    def online_count(self):
        return sum([1 for c in self.contracts if c.online])

    @online_count.expression
    def online_count(cls):
        return func.sum(func.IF(Contract.online, 1, 0))

    @hybrid_property
    def online_size(self):
        return sum([c.size for c in self.contracts if c.online])

    @online_size.expression
    def online_size(cls):
        return func.sum(func.IF(Contract.online, File.__table__.c.size, 0))


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
                           lazy='joined',
                           backref=db.backref('contracts',
                                              lazy='joined',
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

    @hybrid_property
    def online(self):
        return self.expiration > datetime.utcnow()

    @online.expression
    def online(cls):
        return Contract.expiration > datetime.utcnow()


def update_uptime_summary():
    """Moves add any online time from any uncached contracts
    to the uptime for their token.  Then marks them as cached.
    """
    tokens = Token.__table__
    files = File.__table__
    contracts = Contract.__table__

    cache_stmt = select([tokens.c.id,
                         tokens.c.start,
                         tokens.c.end,
                         tokens.c.upsum])

    cache_info = db.engine.execute(cache_stmt).fetchall()

    # fetch all the uncached contracts
    uncached_stmt = select([contracts.c.id,
                            contracts.c.token_id,
                            Contract.expiration.label('expiration'),
                            contracts.c.start,
                            contracts.c.cached]).\
        select_from(contracts.join(files)).\
        where(contracts.c.cached == false())

    uncached = db.engine.execute(uncached_stmt).fetchall()

    # map the uncached contracts to their tokens
    # for fast reference
    uncached_contracts = dict()

    if (len(uncached) > 0):
        for u in uncached:
            uncached_contracts.setdefault(u.token_id, list()).append(u)

    new_cache = list()
    new_summary = list()

    # calculate uptime for each farmer
    for token in cache_info:
        # ensure that we have a start date for this token
        if (token.start is None):
            if (token.id in uncached_contracts):
                start = min(
                    [x.start for x in uncached_contracts[token.id]])
            else:
                # we have to look in all contracts, not just uncached ones
                # this should rarely, if ever, be called.
                # the only time this will be called is if a token exists
                # and either all its contracts are cached but it has no
                # start time or it has no contracts, in which case its
                # uptime will be 0 and remain zero.  so let's just continue
                # instead of trying to select contracts that don't exist
                # this is tested in test_api_status_list_empty_token but
                # is optimized out so will not be seen by coverage
                continue  # pragma: no cover
                # first_contract = db.engine.execute(
                #     select([func.min(contracts.c.start).label('start')])
                #     .where(contracts.c.token_id == token.id))\
                #     .fetchone()
                # start = first_contract.start
        else:
            start = token.start

        # calculate the new uptime stats given the summary
        # and any uncached contracts associated with this token
        calc = UptimeCalculator(
            uncached_contracts.get(token.id, list()),
            UptimeSummary(start, token.end, token.upsum))

        summary = calc.update()

        # update whether contracts have been cached or not
        for c in calc.newly_cached:
            new_cache.append({'contract_id': c})

        # and update the summary
        new_summary.append({'token_id': token.id,
                            'start': summary.start,
                            'end': summary.end,
                            'upsum': summary.uptime})

    if (len(new_cache) > 0):
        s = contracts.update().where(contracts.c.id == bindparam('contract_id')).\
            values(cached=True)

        db.engine.execute(s, new_cache)

    if (len(new_summary) > 0):
        s = tokens.update().where(tokens.c.id == bindparam('token_id')).\
            values(start=bindparam('start'),
                   end=bindparam('end'),
                   upsum=bindparam('upsum'))

        db.engine.execute(s, new_summary)
