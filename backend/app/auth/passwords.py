"""Password hashing with Argon2 via pwdlib (feature 002, FR-003, research R1, R5).

Passwords are never stored or logged; only their Argon2 hashes are.
"""

import secrets

import anyio

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()  # Argon2 with pwdlib's recommended settings

# A real Argon2 hash of a random, discarded secret: logins for unknown emails verify against it,
# so they take as long as logins for real accounts and don't reveal which emails exist (R5).
DUMMY_HASH: str = _hasher.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    """Return a salted Argon2 hash of the password, for storing in users.password_hash."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """True only if the password matches the stored hash."""
    return _hasher.verify(password, password_hash)


# Argon2 deliberately takes tens of milliseconds and ~64 MiB per check, so it runs in a worker
# thread (keeping the server responsive) and at most 4 at a time (bounding memory).
_ARGON2_SLOTS = anyio.CapacityLimiter(4)


async def check_password(password: str, password_hash: str) -> bool:
    """verify_password off the event loop, for request handlers."""
    return await anyio.to_thread.run_sync(
        verify_password, password, password_hash, limiter=_ARGON2_SLOTS
    )
