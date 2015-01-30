#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Runs the development server of the downstream_node app.
# Not for production use.

import argparse
import csv
import time
from flask import Flask, jsonify
from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware
from datetime import datetime, timedelta
from sqlalchemy import select, engine, update, insert, bindparam, true, func, and_

from downstream_node.startup import app, db
from downstream_node.models import Contract, Address, Token, File, Chunk
from downstream_node import node
from downstream_node.utils import MonopolyDistribution, Distribution

def initdb():   
    db.create_all()


def cleandb():
    # delete expired contracts and files
    s = Contract.__table__.delete().where(Contract.cached == true())
    
    db.engine.execute(s)
    
    # and delete unreferenced files
    s = File.__table__.delete().where(~File.__table__.c.id.in_(select([Contract.__table__.c.file_id])
                                                               .union(
                                                               select([Chunk.__table__.c.file_id]))))
    
    db.engine.execute(s)

def get_available_sizes():
    available_sizes_stmt = select([File.__table__.c.size]).select_from(Chunk.__table__.join(File.__table__))
    available_sizes_result = db.engine.execute(available_sizes_stmt).fetchall()
    available_sizes = [a[0] for a in available_sizes_result]
    return available_sizes
    
def maintain_capacity(min_chunk_size, max_chunk_size, size, base=2):
    # maintains a certain size of available chunks
    while(1):
        available_sizes = get_available_sizes()
        available_dist = Distribution(from_list=available_sizes)
        # print('Sizes already available: {0}'.format(available_dist))
        # print('Total size available: {0}'.format(available_dist.get_total()))
        dist = MonopolyDistribution(min_chunk_size, max_chunk_size, size, base)
        # print('Desired distribution: {0}'.format(dist))
        missing = dist.subtract(available_dist)
        # print('Missing: {0}'.format(missing))
        missing_list = missing.get_list()
        if (len(missing_list) > 0):
            print('Generating chunks: {0}'.format(missing_list))
        for chunk_size in sorted(missing_list, reverse=True):
            generate_chunks(chunk_size)
        if (len(missing_list) > 0):
            print('Done.')
        time.sleep(2)
    
def generate_chunks(size, number=1):
    # generates a test chunk
    for i in range(0,number):
        node.generate_test_file(size)


def updatewhitelist(path):
    with open(path,'r') as f:
        r = csv.reader(f)
        next(r)
        updated=list()
        for l in r:
            s = Address.__table__.select().where(Address.address == l[0])
            result = db.engine.execute(s).first()                
            if (result is not None):
                db.engine.execute(Address.__table__.update().\
                    where(Address.id == result.id).\
                    values(crowdsale_balance=int(l[1])))
            else:
                db.engine.execute(Address.__table__.insert().\
                    values(address=l[0], crowdsale_balance=l[1]))
                result = db.engine.execute(Address.__table__.select().\
                    where(Address.address == l[0])).first()
            updated.append(result.id)
        all = db.engine.execute(Address.__table__.select()).fetchall()
        for row in all:
            if (row.id not in updated):
                # also recursively delete all tokens associated with that address
                tbd_tokens = db.engine.execute(Token.__table__.select().\
                    where(Token.address_id == row.id)).fetchall()
                for t in tbd_tokens:
                    # and all contracts associated with that address                        
                    db.engine.execute(Contract.__table__.delete().\
                        where(Contract.token_id == t.id))
                    db.engine.execute(Token.__table__.delete().\
                        where(Token.id == t.id))
                db.engine.execute(Address.__table__.delete().\
                    where(Address.id == row.id))


def eval_args(args):
    if args.initdb:
        initdb()
    elif args.cleandb:
        cleandb()
    elif (args.whitelist is not None):
        updatewhitelist(args.whitelist)
    elif (args.generate_chunk is not None):
        generate_chunks(args.generate_chunk)
    elif (args.maintain is not None):
        print('Maintaining total size: {0}, min chunk size: {1}, max chunk size: {2}'.format(
            args.maintain[2],
            args.maintain[0],
            args.maintain[1]))
        maintain_capacity(int(args.maintain[0]), int(args.maintain[1]), int(args.maintain[2]))
    else:
        debug_root = Flask(__name__)
        debug_root.debug = True
        debug_root.add_url_rule('/','index',lambda: jsonify(msg='debugging'))
        prefixed_app = DispatcherMiddleware(debug_root, {app.config['APPLICATION_ROOT']:app})
        run_simple('localhost', 5000, prefixed_app, use_reloader=True)


def parse_args():
    parser = argparse.ArgumentParser('downstream')
    parser.add_argument('--initdb', action='store_true')
    parser.add_argument('--cleandb', action='store_true')
    parser.add_argument('--whitelist', help='updates the white list '
        'in the db and exits from a whitelist csv file.  each row except'
        'the first should be in the format\n'
        '"address","crowdsale_balance",...\n'
        'and the first row will be skipped.')
    parser.add_argument('--generate-chunk', help='Generates a test chunk of'
        'specified size.', type=int)
    parser.add_argument('--maintain', help='Maintain available chunk capacity'
        'Specify three values (min chunk size, max chunk size, total pre-gen '
        'size)', nargs=3)
    return parser.parse_args()


def main():
    args = parse_args()
    eval_args(args)


if __name__ == '__main__':
    main()
