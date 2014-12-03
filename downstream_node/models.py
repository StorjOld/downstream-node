#!/usr/bin/env python
# -*- coding: utf-8 -*-
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import exists
from sqlalchemy.sql.expression import false
from datetime import datetime, timedelta

from .startup import db


class File(db.Model):
    __tablename__ = 'files'

    id = db.Column(db.Integer(), primary_key=True, autoincrement=True)
    hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    path = db.Column(db.String(128), unique=True)
    redundancy = db.Column(db.Integer(), nullable=False)
    interval = db.Column(db.Integer(), nullable=False)
    added = db.Column(db.DateTime(), nullable=False)


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
    heartbeat = db.Column(db.PickleType(), nullable=False)
    ip_address = db.Column(db.String(32), nullable=False, index=True)
    farmer_id = db.Column(db.String(20), nullable=False, unique=True)
    hbcount = db.Column(db.Integer(), nullable=False, default=0)
    location = db.Column(db.PickleType())
    # shouldn't need unicode, since it will have come over JSON which will have
    # escaped any unicode characters.  need to test that behavior.
    message = db.Column(db.Text())
    signature = db.Column(db.Text())

    # for uptime cache
    start = db.Column(db.DateTime())
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
        return exists().where(and_(Contract.expiration > datetime.utcnow(),
                                   Contract.token_id == self.id)).\
            label('online')

    @property
    def uptime(self):
        # for c in Contract.query.filter(Contract.token_id == self.id).all():
        #    times[(c.start - datetime.utcnow()).total_seconds()] = 1
        #    times[(c.due - datetime.utcnow() if c.due <
        #           datetime.utcnow() else
        #           timedelta()).total_seconds()] = -1
        # for time in sorted(times):
        #    if (count == 0 and times[time] == 1):
        #        tsum += time
        #    elif (count == 1 and times[time] == -1):
        #        tsum -= time
        #    count += times[time]
        # try:
        #    return tsum / sorted(times)[0]
        # except:
        #    return 0

        # new version

        ref = datetime.utcfromtimestamp(0)
        now = datetime.utcnow()
        count = 0
        times = dict()
        need_to_commit = False

        # pull sum from cache
        tsum = self.upsum
        # and we'll calculate a new cached uptime if we have any new items to
        # be cached
        csum = self.upsum

        uncached = Contract.query.filter(and_(Contract.token_id == self.id,
                                              Contract.cached == false())).\
            all()

        print('Got {0} uncached contracts.'.format(len(uncached)))

        class UptimeCache(object):

            def __init__(self, action, cache):
                self.action = action
                self.cache = cache

        for c in uncached:
            if (c.expiration < datetime.utcnow()):
                # we can cache this contract
                need_to_commit = True
                print('Contract is {0}'.format(
                    'cached' if c.cached else 'uncached'))
                c.cached = True
                times[(c.start - ref)] = UptimeCache(1, True)
                times[(c.expiration - ref)] = UptimeCache(-1, True)
            else:
                times[(c.start - ref)] = UptimeCache(1, False)
                times[(c.expiration - ref if c.expiration <
                       now else
                       now - ref)] = UptimeCache(-1, False)

        stimes = sorted(times)
        for time in stimes:
            # set the start time to the earliest time
            if (self.start is None):
                self.start = ref + time
            if (count == 0 and times[time].action == 1):
                print('u online at: {0}'.format(time))
                tsum -= time
                if (times[time].cache):
                    csum -= time
                print('tsum = {0}'.format(tsum))
            elif (count == 1 and times[time].action == -1):
                print('u offline at: {0}'.format(time))
                tsum += time
                if (times[time].cache):
                    csum += time
                print('tsum = {0}'.format(tsum))
            count += times[time].action

        if (need_to_commit):
            self.upsum = csum
            db.session.commit()

        try:
            earliest = self.start
            print('now = {0}'.format(now))
            print('tsum = {0}'.format(tsum))
            print('earliest = {0}'.format(earliest))
            print('total time = {0}'.format((now - earliest).total_seconds()))
            return tsum.total_seconds() / ((now - earliest).total_seconds())
        except:
            return 0

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
    token_id = db.Column(db.ForeignKey('tokens.id'), index=True)
    file_id = db.Column(db.ForeignKey('files.id'))
    state = db.Column(db.PickleType(), nullable=False)
    challenge = db.Column(db.PickleType())
    tag_path = db.Column(db.String(128), unique=True)
    start = db.Column(db.DateTime())
    due = db.Column(db.DateTime())
    answered = db.Column(db.Boolean(), default=False)
    # for prototyping, include file seed for regeneration, and file size
    seed = db.Column(db.String(128))
    size = db.Column(db.Integer())
    cached = db.Column(db.Boolean(), default=False)

    token = db.relationship('Token',
                            backref=db.backref('contracts',
                                               lazy='dynamic',
                                               cascade='all, delete-orphan'))

    file = db.relationship('File',
                           backref=db.backref('contracts',
                                              lazy='dynamic',
                                              cascade='all, delete-orphan'))

    __table_args__ = (
        db.Index('ix_contracts_token_id_file_id', 'token_id', 'file_id'), )

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
