#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Runs the development server of the downstream_node app.
# Not for production use.

import argparse
from datetime import datetime, timedelta

from downstream_node.startup import app, db
from downstream_node.models import Contract

def initdb():   
    db.create_all()


def cleandb():
    # delete old contracts
    Contract.query.filter(Contract.due < datetime.utcnow()-timedelta(seconds=60)).delete()
    db.session.commit()


def eval_args(args):
    if args.initdb:
        initdb()
    elif args.cleandb:
        cleandb()
    else:
        app.run(debug=True)


def parse_args():
    parser = argparse.ArgumentParser('downstream')
    parser.add_argument('--initdb', action='store_true')
    parser.add_argument('--cleandb', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    eval_args(args)


if __name__ == '__main__':
    main()
