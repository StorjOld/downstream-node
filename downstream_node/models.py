#!/usr/bin/env python
# -*- coding: utf-8 -*-
from sqlalchemy import select, func, and_, text, desc
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import exists
from sqlalchemy.sql.expression import false, true
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
        ref = datetime.utcfromtimestamp(0)
        now = datetime.utcnow()
        count = 0
        times = list()
        need_to_commit = False

        # pull sum from cache
        tsum = self.upsum
        # print('Pulled upsum: {0}'.format(self.upsum))

        # last cached
        lcache = Contract.query.filter(and_(Contract.token_id == self.id,
                                            Contract.cached == true())).\
            order_by(desc(Contract.due)).first()

        if (lcache is not None):
            last_time = lcache.expiration
        else:
            last_time = ref

        uncached = Contract.query.filter(and_(Contract.token_id == self.id,
                                              Contract.cached == false())).\
            all()

        # small class to handle calculation of uptime
        class UptimeEvent(object):

            def __init__(self, time, action):
                """
                Initialization method

                :param time: the time the event occurs
                :param action: integer representing whether the farmer goes
                    online or offline.  1 = online.  -1 = offline
                """
                self.time = time
                self.action = action

        for c in uncached:
            if (c.expiration < now):
                # we can cache this contract
                need_to_commit = True
                c.cached = True
                times.append(UptimeEvent(c.start - ref, 1))
                times.append(UptimeEvent(c.expiration - ref, -1))
                # and upsum will increase if this contract had any additional
                # uptime past last cache point
                corrected_start = (
                    c.start if c.start >= last_time else last_time)
                duration = c.expiration - corrected_start \
                    if corrected_start > c.expiration \
                    else timedelta(seconds=0)
                self.upsum += duration
            else:
                times.append(UptimeEvent(c.start - ref, 1))
                times.append(UptimeEvent(
                    (c.expiration - ref
                     if c.expiration < now
                     else now - ref), -1))

        # print('Looking at {0} events.'.format(len(times)))
        sevents = sorted(times, key=lambda x: x.time)
        for event in sevents:
            # print('Analyzing event at time {0}, {1}'.format(
            #    event.time, event.action))
            # set the start time to the earliest time
            if (self.start is None):
                self.start = ref + event.time
                need_to_commit = True
            # check if the farmer is going online
            if (event.action == 1):
                if (count == 0):
                    # subtract start time (duration = final - initial)
                    tsum -= event.time
            # check if the farmer is going offline
            elif (event.action == -1):
                if (count == 1):
                    # if so, add final time
                    tsum += event.time
            # we keep track of the number of contracts that are online
            count += event.action
            # print('Status: tsum: {0}, count: {1}'.format(tsum, count))

        if (need_to_commit):
            # print('Committing upsum: {0}'.format(self.upsum))
            db.session.commit()

        try:
            # print('Up time: {0}, total time: {1}'.format(
            #    tsum, (now - self.start)))
            return tsum.total_seconds() / ((now - self.start).total_seconds())
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
