#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Runs the development server of the downstream_node app.
# Not for production use.

import argparse
import csv
from datetime import datetime, timedelta
from sqlalchemy import select, engine, update, insert

from downstream_node.startup import app, db
from downstream_node.models import Contract, Address

def initdb():   
    db.create_all()


def cleandb():
    # delete old contracts
    Contract.query.filter(Contract.due < datetime.utcnow()
                          -timedelta(seconds=60)).delete()
    db.session.commit()

def addwhitelist(path):
    with open(path,'r') as f:
            r = csv.reader(f)
            next(r)
            for l in r:
                s = Address.__table__.select().where(Address.address == l[0])
                result = db.engine.execute(s).first()
                if (result is not None):
                    db.engine.execute(Address.__table__.update().\
                        where(Address.id == result.id).\
                        values(crowdsale_balance=int(l[1])))
                else:
                    db.engine.execute(Address.__table__.insert().\
                        values(address=l[0], crowdsale_balane=l[1]))
def eval_args(args):
    if args.initdb:
        initdb()
    elif args.cleandb:
        cleandb()
    elif (args.whitelist is not None):
        addwhitelist(args.whitelist)
    else:
        app.run(debug=True)


def parse_args():
    parser = argparse.ArgumentParser('downstream')
    parser.add_argument('--initdb', action='store_true')
    parser.add_argument('--cleandb', action='store_true')
    parser.add_argument('--whitelist', help='loads white list specified '
                                            'into db and exits')
    return parser.parse_args()


def main():
    args = parse_args()
    eval_args(args)


if __name__ == '__main__':
    main()
