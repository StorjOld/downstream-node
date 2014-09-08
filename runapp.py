#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Runs the development server of the downstream_node app.
# Not for production use.

import argparse

from downstream_node.startup import app, db


def initdb(sys=None):
    db.engine.execute("CREATE DATABASE downstream")
    db.create_all()


def eval_args(args):
    if args.initdb:
        initdb()
    else:
        app.run(debug=True)


def parse_args():
    parser = argparse.ArgumentParser('downstream')
    parser.add_argument('--initdb', action='store_true')
    return parser.parse_args()


def main():
    args = parse_args()
    eval_args(args)


if __name__ == '__main__':
    main()
