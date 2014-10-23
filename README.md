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

Get libcrypto which is required for some dependencies of downstream-node.

```
$ apt-get install libcrypto++-dev
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

It is necessary to pull in the IP lookup database from maxmind:

```
mkdir data && cd data
curl -o GeoLite2-City.mmdb.gz http://geolite.maxmind.com/download/geoip/database/GeoLite2-City.mmdb.gz
gunzip GeoLite2-City.mmdb.gz
cd ..
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
	"size": 1000,
    "tag": "...tag object string representation..."
}
```

In the future the new chunk contract route will have a parameter for desired size.  Then this function will return an (possibly empty) array of chunk contracts with total size not exceeding the size requested.

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

Finally, some statistics about the node can be retrieved through a status API as follows.

The status API is required to produce the following information for each farmer:

1. Farmer ID (token hash)
2. SJCX address
3. Geographic Location
4. Percentage uptime since creation
5. Number of heartbeats completed
6. Whether the farmer is currently online
7. A hash of the IP address of the farmer
8. Total data size hosted by the farmer in bytes

The list of all farmer ids can be retrieved with

     GET /api/downstream/status/list

which returns all the farmers ids

```json
{
   "farmers":
   [
      "fa1e4944e48ed7bd3739",
      "997e717ba92078118cce",
      "0f297828e2a687943fc4",
      "81b6a0d841a3184028e6",
      "49eb47ea315d53399f69",
      "b2ca01ff2113559b231d",
      "68ff46d440255ac29a3c",
      "479935fca9ce02f62788",
      "33d63de99f0aad6279ba",
      "8088d59b6adf8faf9974",
      "ddbeb08b93b1d06e9939",
      "e7a5558e62d315a54058",
      "1de67bc29901db705ea1",
      "e94902cda505de115027",
      "c9c1f91a6362af0babad",
      "e87f8117d0d10a8d6479",
      "5f652023fb6b8034fb5c",
      "b05bd26f9f28035a3006",
      "e78d8f0edd1a50bce83b",
      "dc4ce32c7c8a7d0a3cb9"
   ]
}
```

Optionally, one may sort in ascending order by `id`, `address`, `uptime`, `heartbeats`, `iphash`, `contracts`, `size`, or `online` by using

    GET /api/downstream/status/list/by/<sortby>

or in descending order

    GET /api/downstream/status/list/by/d/<sortby>

It is also possible to limit the number of responses

    GET /api/downstream/status/list/by/<sortby>/<limit>

and specify a page number

    GET /api/downstream/status/list/by/<sortby>/<limit>/<page>

So some examples

    GET /api/downstream/status/list/by/d/uptime/25

will return the 25 farmers with the highest uptime percentage

    GET /api/downstream/status/list/by/d/contracts/15/2

will return the third page (rows 30-44) of the farmers with the most contracts.

And then the individual farmer information can be retrieved with:

    GET /api/downstream/status/show/<id>

```json
{
      "id": "45bd945fa10e3f059834",
      "address": "18d6KhnTg9dM9jtb1MWXdbibu3Pwt1QHQt",
      "location": {"city": "West Jerusalem", "country": "Israel", "lon": 35.21961, "zip": "", "state": "Jerusalem District", "lat": 31.78199},
      "uptime": 96.015,
      "heartbeats": 241,
      "iphash": "d55529c83953e218cc58",
      "contracts": 2,
      "size": 200,
      "online": true
}
```

Planning on making the id the first 20 characters of the hex representation of the token hash.

Will probably cache the farmer list on the server side to improve performance.

This product includes GeoLite2 data created by MaxMind, available from [http://www.maxmind.com](http://www.maxmind.com).