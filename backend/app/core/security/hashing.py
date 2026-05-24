"""Password hashing via argon2id.

Argon2id is the OWASP-recommended default for new applications. ``argon2-cffi``
ships with sensible parameters (RFC 9106 second recommended profile); we keep
them and re-tune later only if perf demands it.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError


_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    """Return an argon2id hash safe to store in the database."""
    if not plain:
        raise ValueError("password must not be empty")
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time compare. Returns False on mismatch or malformed hash."""
    if not plain or not hashed:
        return False
    try:
        return _hasher.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHash):
        return False


def needs_rehash(hashed: str) -> bool:
    """True if the hash uses outdated params and should be re-hashed on next login."""
    try:
        return _hasher.check_needs_rehash(hashed)
    except InvalidHash:
        return True
