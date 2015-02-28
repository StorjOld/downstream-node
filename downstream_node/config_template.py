#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import heartbeat

# Flask
DEBUG = True
SECRET_KEY = os.urandom(32)
"""Where the application is mounted."""
APPLICATION_ROOT = '/api/downstream/v1'
"""The server alias, used for MONGO logging"""
SERVER_ALIAS = 'dsnode'

"""The SQLALCHEMY database uri"""
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://localhost/downstream'  # NOQA

"""Not used, but theoretically where staging files will be placed"""
FILES_PATH = 'tmp/'
"""Where tags are placed"""
TAGS_PATH = 'tags/'
"""The path to the MMDB database used for locating IP addresses
geographically"""
MMDB_PATH = 'data/GeoLite2-City.mmdb'

"""The type of heartbeat to use
The heartbeat we use should probably eventually be associated with
the uploading user so they can decide on the check_fraction..."""
HEARTBEAT = heartbeat.Merkle.Merkle
"""The path where the heartbeat will be stored so that on shutdowns
the same secret key is maintained."""
HEARTBEAT_PATH = 'data/heartbeat'

"""Whether to log each action on the node"""
MONGO_LOGGING = False
"""Uri to use for logging"""
MONGO_URI = 'mongodb://localhost/dsnode_log'
"""Whether to profile each request.  Requires MONGO_LOGGING to be true"""
PROFILE = False

"""The default chunk size that will be returned if no size is specified"""
DEFAULT_CHUNK_SIZE = 33554432
"""Maximum number of tokens allowed per IP address"""
MAX_TOKENS_PER_IP = 5
"""Minimum crowdsale_balance value in the whitelist"""
MIN_SJCX_BALANCE = 10000
"""Maximum number of characters in the signature message"""
MAX_SIG_MESSAGE_SIZE = 1024
"""Whether a signature is required to prove whitelist authority"""
REQUIRE_SIGNATURE = True
"""The default interval for test files"""
DEFAULT_INTERVAL = 300
"""Maximum number of chunks each /chunk/ request will return"""
MAX_CHUNKS_PER_REQUEST = 10
"""Maximum size that an address can be farming on this prototype node"""
MAX_SIZE_PER_ADDRESS = 1073741824

"""The heartbeat check fraction: the fraction of the chunk that is
checked on each heartbeat
Changing this requires deleting the data/heartbeat file
and rebuilding the chunk database.  Make sure
the chunk maintainer is not running, and delete the heartbeat
file (see HEARTBEAT_PATH)
Then use
    python runapp.py --clearchunks
to clear the DB chunks and tags."""
HEARTBEAT_CHECK_FRACTION = 0.01
