#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import os
import pickle
import unittest
import random

from  datetime import datetime, timedelta

from heartbeat import Heartbeat
from RandomIO import RandomIO
from downstream_node.startup import app, db
from downstream_node import models
from downstream_node.lib import node, utils
from downstream_node.config import config
from downstream_node.models import Files, Addresses, Tokens, Contracts
from sqlalchemy import func

# generate some random data for our tests

db.engine.execute('DROP TABLE contracts,tokens,addresses,files')
db.create_all()

test_address = '13FfNS1wu6u7G9ZYQnyxYP1YRntEqAyEJJ'
        
address = Addresses(address=test_address)
db.session.add(address)
db.session.commit()

for i in range(0,10):
    path = RandomIO().genfile(1000,'files/')
    hash = node.add_file(path)
    
    db_file = Files.query.filter(Files.hash==hash).first()
    
    # randomly add a couple of contracts for this file
    n = random.randint(0,3)
    for j in range(0,n):
        token = node.create_token(test_address)
        
        db_token = Tokens.query.filter(Tokens.token==token).first()
        
        beat = pickle.loads(db_token.heartbeat)
        
        with open(path,'rb') as f:
            (tag,state) = beat.encode(f)
            
        chal = beat.gen_challenge(state)
        
        contract = Contracts(token = token,
                             file = hash,
                             state = pickle.dumps(state),
                             challenge = pickle.dumps(chal),
                             expiration = datetime.utcnow() + timedelta(seconds = db_file.interval))
                             
        db.session.add(contract)
        db.session.commit()
                             
# attempt the join...
candidates = db.session.query(Files,func.count(Contracts.file)).outerjoin(Contracts).group_by(Files.hash).all()

candidates.sort(key = lambda x: x[0].added)
candidates.sort(key = lambda x: x[1])

for f in candidates:
    print(f[0].hash,f[0].added,f[1])

db.session.close()