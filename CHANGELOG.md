# downstream-node Changelog

### Master

### v0.1.7

* [ENHANCEMENT] Supported streaming of challenges and chunks to speed up responsiveness of server.

### v0.1.6

* [ENHANCEMENT] Multiple contracts handled per request

### v0.1.5

* [ENHANCEMENT] Made contract count and contract size be the online count and size, not total, for a nicer dashboard experience
* [BUGFIX] Fixed bug where heartbeat state was not being updated in the database, and so the same challenge was being answered over and over (for Merkle)
* [ENHANCEMENT] Modified --maintain option so that software will maintain a diverse set of chunk sizes
* [ENHANCEMENT] Restructured so that chunk/shards can be pre-generated before being requested in a contract
* [ENHANCEMENT] Added --generate-chunk option to runapp.py in order to pre-generate chunks
* [ENHANCEMENT] Added --maintain option to runapp.py for maintaining a certain size of pre-generated chunks.
* [OPTIMIZATION] Moved to an app wide heartbeat so that we don't have to regenerate every time a new token is requested
* [OPTIMIZATION] Moved to chunk-wise hash and tag for chunks so that we can generate very large chunks without needing a large amount of memory.

### v0.1.3-alpha

* [ENHANCEMENT] Switched to changelog methodology
* [ENHANCEMENT] Added ability to specify how many tokens are allowed per IP address
* [ENHANCEMENT] Added signature checking for verifying ownership of addresses

### v0.1-alpha

* Initial alpha release