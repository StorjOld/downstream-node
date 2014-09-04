#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Runs the development server of the downstream_node app.
# Not for production use.

from downstream_node.startup import app


def main():
    app.run(debug=True)

if __name__ == '__main__':
    main()