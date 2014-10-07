downstream-node
===============

Master: [![Build Status](https://travis-ci.org/Storj/downstream-node.svg?branch=master)](https://travis-ci.org/Storj/downstream-node) [![Coverage Status](https://img.shields.io/coveralls/Storj/downstream-node.svg)](https://coveralls.io/r/Storj/downstream-node?branch=master)
Devel: [![Build Status](https://travis-ci.org/Storj/downstream-node.svg?branch=devel)](https://travis-ci.org/Storj/downstream-node) [![Coverage Status](https://img.shields.io/coveralls/Storj/downstream-node.svg)](https://coveralls.io/r/Storj/downstream-node?branch=devel)

The server-side stuff for [downstream](https://github.com/Storj/downstream).  Includes the library and API.

## What is this I don't even?

`downstream-node` is the server to [downstream-farmer](https://github.com/Storj/downstream-farmer).  Yep, it a client/server relationship. `downstream-node` requires MySQL and a working config.

*The implied first step is to download and install MySQL server.*  For example, on Ubuntu:

```
$ apt-get -y install mysql-server
```

Get `downstream-node`:

```
$ git clone -b devel https://github.com/Storj/downstream-node.git
$ cd downstream-node
$ pip install -r requirements.txt .
```

Set up the database:

```
mysql> create database downstream;
mysql> create user 'downstream'@'localhost' identified by 'password';
mysql> grant all on downstream.* to 'downstream'@'localhost';
mysql> flush privileges;
```


Edit the config with the appropriate details:

```
$ vim downstream_node/config/config.py
```

Modify the database line for the user configuration we just created in MySQL:

```
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://downstream:password@localhost/downstream'
```

Create the DB schema, and start the server in development mode (bound to localhost:5000):

```
$ python runapp.py --initdb
$ python runapp.py
```

**If this is at all confusing, we're doing it as a functional test in the travis.yml file, so watch it in action on Travis-CI.**

downstream
==========
Web application where the client downloads and proves file existence to a single node. Used mostly on Metadisk nodes or standalone verification nodes.
 
*Note: This is a proof of concept intended to be used to collect uptime and redundancy statistics. It should not be used for production services as authentication keys are passed in plaintext. Furthermore, data should not be passed from node to client to prevent arbitrary code execution until proper sandboxing is place.*
 

#### Node library functions
The following functions are available in this prototype

```python
create_token(sjcx_address)
    """Creates a token for the given address. For now, addresses will not be enforced, and anyone
    can acquire a token.

    :param sjcx_address: address to use for token creation.  for now, just allow any address.
    :returns: the token
    """

delete_token(token)
    """Deletes the given token.

    :param token: token to delete
    """

get_chunk_contract(token)
    """In the final version, this function should analyze currently available file chunks and 
    disburse contracts for files that need higher redundancy counts.  
    In this prototype, this function should generate a random file with a seed.  The seed 
    can then be passed to a prototype farmer who can generate the file for themselves.  
    The contract will include the next heartbeat challenge, and the current heartbeat state 
    for the encoded file.

   :param token: the token to associate this contract with
   :returns: the chunk
     """

verify_proof(token,file_hash,proof)
    """This queries the DB to retrieve the heartbeat, state and challenge for the contract id, and 
    then checks the given proof.  Returns true if the proof is valid.

    :param token: the token for the farmer that this proof corresponds to
    :param file_hash: the file hash for this proof
    :param proof: a heartbeat proof object that has been returned by the farmer
    :returns: boolean true if the proof is valid, false otherwise
    """
```

#### Database Tables
To write these functions the database models have to be modified to include contracts and tokens tables.

#### HTTP Routes
Additionally the following prototype routes should be exposed for the public API:

Get a new token for a given address.  For now, don't check address, just return a token.

    GET /api/downstream/new/<sjcx_address>
Response:
```
{
    "token": "ceb722d954ef9d1af3eed2bbe0aeb954",
    "heartbeat": "...heartbeat object string representation..."
}
```

Get a new chunk contract for a token.  Only allow one contract per token for now.  Returns the first challenge and expiration, the file hash, a seed for generation of the prototype file, and the file heartbeat tag.

    GET /api/downstream/chunk/<token>
Response:
```
{
    "challenge": "...challenge object string representation...",
    "expiration": "2014-10-03 17:29:01",
    "file_hash": "012fb25d2f14bb31bcbad5b8d99703114ed970601b21142c93b50421e8ddb0d7",
    "seed": "70aacdc6a2f7ef0e7c1effde27299eda",
	"size": "1000",
    "tag": "...tag object string representation..."
}
```

Gets the currently due challenge for this token and file hash.

    GET /api/downstream/challenge/<token>/<file_hash>
Response:
```
{
   "challenge": "...challenge object string representation...",
   "expiration": "2014-10-03 17:29:01",
}
```

Posts an answer for the current challenge on token and file hash.

    POST /api/downstream/answer/<token>/<file_hash>
Parameters:
```
{
    "proof": "...proof object string representation..."
}
```
Response:
```
{
    "status": "ok"
}
```
