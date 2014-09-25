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
$ git clone https://github.com/Storj/downstream-node.git
$ cd downstream-node
$ pip install -r requirements.txt
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
 

## Node Private Functions

### Create Token
Creates a random secret token, and stores in the database. This serves as the identification and authorization key for the particular address. A particular address may create multiple tokens. Files are pegged to the authentication token not the address. This function should reject an address if it is not listed in the address whitelist from the crowdsale.

    create_token(sjcx_address)

### Delete Token
Removes the token from the database, and reassigns any chunks associated with it.

    delete_token(token)

### Add File
This is a multi-step process where we add a file to a list of files that we monitor. If this is a Metadisk node we simply pass the encrypted file chunk, if it is not then we have to pass it though our encrypting and hashing progress. After uploading we need to generate a series of hash challenges.  

    add_file(chunk_path, redundancy, interval)

### Remove File
Remove the file from the list of files that we monitor.

    remove_file(chunk_hash)

### Generate Challenges
Using the [heartbeat](https://github.com/storj/heartbeat) lib we can generate and store the hash challenges for our file. We should also store the merkle root of our challenges. 

    gen_challenges(file_path, root_seed)

### Update Challenges
Update and validate the current challenges

    update_challenges()

## Node Public API

### New Token 
Provides a client with a new random secret token associated on the with the passed address. 
    
    GET /api/downstream/new/<sjcx_address>

```
dfs9mfa2
```

### Get Chunk Contract

Gives the farmer a data contract. Allow the client to download another chunk of data, including how often the server will check for the data (specified in seconds), and the initial challenge. ** Don't actually implement this fully yet. See prototype functions below.**

    GET /api/downstream/chunk/<token>

```json
{
    "url": "http://node1.storj.io/api/download/05ecf7f9d218c631cc380527ac57f72798647824aa8839eb82045ed9fc3360c7",
    "file_hash": "05ecf7f9d218c631cc380527ac57f72798647824aa8839eb82045ed9fc3360c7", 
    "challenge": "0.012381234",
    "interval": 60
}
```
Possible errors:
```json
{ "status": "no_chunks" }
{ "status": "no_token" }
{ "status": "error" }
```

### End Chunk Contract 

Client removing a chunk from its list.

    GET /api/downstream/remove/<token>/<file_hash>
```json
{ "status": "ok" }
```
Possible errors:
```json
{ "status": "no_token" }
{ "status": "no_hash" }
{ "status": "error" }
```

### Chunk Contract Status

Gets the current contract statuses from the perspective of the node. 

    GET /api/downstream/due/<account token>

```json
{
    "all_contracts":[
        {"hash": "05ecf7f9d218c631cc380527ac57f72798647824aa8839eb82045ed9fc3360c7"},
        {"hash": "fc3d80e28d20a3db5576b8b7fd66176a3a9a857ca89b8cec4b3b832aafc77c8a"}],
    "due_contracts":[
        {"hash": "05ecf7f9d218c631cc380527ac57f72798647824aa8839eb82045ed9fc3360c7", "challenge": "0.012381234"},
        {"hash": "fc3d80e28d20a3db5576b8b7fd66176a3a9a857ca89b8cec4b3b832aafc77c8a", "challenge": "0.034385411"}]
}
```

### Answer Chunk Contract

Allows the client to answer a challenge.

    GET /api/downstream/challenge/<token>/<file_hash>/<hash_response>

```json
{"status": "pass"}
{"status": "fail"}
```
