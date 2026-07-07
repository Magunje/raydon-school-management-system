import hashlib

def _ctr_keystream(secret_key, length):
    """Generates a keystream of specified length using SHA256 in counter mode."""
    keystream = bytearray()
    counter = 0
    while len(keystream) < length:
        counter_bytes = counter.to_bytes(8, byteorder="big")
        block = hashlib.sha256(secret_key + counter_bytes).digest()
        keystream.extend(block)
        counter += 1
    return bytes(keystream[:length])


def encrypt(plain_text, secret_key_str):
    """Encrypts plain_text and returns hex prefixed with 'enc:'."""
    if not plain_text:
        return ""
    plain_bytes = str(plain_text).encode("utf-8")
    key_bytes = hashlib.sha256(secret_key_str.encode("utf-8")).digest()
    
    keystream = _ctr_keystream(key_bytes, len(plain_bytes))
    cipher_bytes = bytes(p ^ k for p, k in zip(plain_bytes, keystream))
    return "enc:" + cipher_bytes.hex()


def decrypt(cipher_text, secret_key_str):
    """Decrypts cipher_text if it starts with 'enc:' prefix."""
    if not cipher_text or not str(cipher_text).startswith("enc:"):
        return cipher_text
    try:
        cipher_bytes = bytes.fromhex(cipher_text[4:])
        key_bytes = hashlib.sha256(secret_key_str.encode("utf-8")).digest()
        
        keystream = _ctr_keystream(key_bytes, len(cipher_bytes))
        plain_bytes = bytes(c ^ k for c, k in zip(cipher_bytes, keystream))
        return plain_bytes.decode("utf-8")
    except Exception:
        return cipher_text
