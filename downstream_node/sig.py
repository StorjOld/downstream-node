from pycoin.ecdsa import *
from pycoin.encoding import *
import base64

def int_to_var_bytes(x):
    if x < 253: return intbytes.to_bytes(x,1)
    elif x < 65536: return bytearray([253]) + intbytes.to_bytes(x,2)[::-1]
    elif x < 4294967296: return bytearray([254]) + intbytes.to_bytes(x,4)[::-1]
    else: return bytearray([255]) + intbytes.to_bytes(x,8)[::-1]

def bitcoin_sig_hash(message):
    padded = b'\x18Bitcoin Signed Message:\n' + int_to_var_bytes(len(message)) + message
    return double_sha256(padded)

def verify(message, signature, address):
    binsig = base64.b64decode(signature)

    r = intbytes.from_bytes(binsig[1:33])

    s = intbytes.from_bytes(binsig[33:65])

    val = intbytes.from_bytes(bitcoin_sig_hash(message.encode()))

    pubpairs = possible_public_pairs_for_signature(generator_secp256k1, val, (r,s))

    addr_hash160 = bitcoin_address_to_hash160_sec(address)

    for pair in pubpairs:
        if (public_pair_to_hash160_sec(pair) == addr_hash160):
            return True

    return False
