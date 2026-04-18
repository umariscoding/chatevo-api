"""
Symmetric encryption for secrets stored at rest.

Fernet (AES-128-CBC + HMAC-SHA256) keyed by VOICE_ENCRYPTION_KEY. The env var
holds a urlsafe-base64-encoded 32-byte key; generate one with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.

Encrypted values are stored as urlsafe-base64 strings. Decrypting with the
wrong key raises InvalidToken; callers should surface that as a config error.
"""

import os
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


class EncryptionNotConfigured(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = os.getenv("VOICE_ENCRYPTION_KEY")
    if not key:
        raise EncryptionNotConfigured(
            "VOICE_ENCRYPTION_KEY is not set. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext: Optional[str]) -> Optional[str]:
    if plaintext is None or plaintext == "":
        return None
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: Optional[str]) -> Optional[str]:
    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Failed to decrypt stored secret; check VOICE_ENCRYPTION_KEY") from exc
