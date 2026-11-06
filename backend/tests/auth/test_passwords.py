"""app.auth.passwords: Argon2 hashing (feature 002, task T009, FR-003, research R1, R5)."""

import pytest

from app.auth.passwords import DUMMY_HASH, hash_password, verify_password

PASSWORD = "correct horse battery staple"


def test_hash_is_argon2_and_never_the_password() -> None:
    """Fails if the stored form is (or contains) the password, or isn't an Argon2 hash."""
    hashed = hash_password(PASSWORD)

    assert hashed.startswith("$argon2")
    assert PASSWORD not in hashed


def test_same_password_hashes_differently_each_time() -> None:
    """Fails if hashes aren't salted (equal passwords would be visible in the database)."""
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_correct_password_verifies() -> None:
    """Fails if a user can't log in with their own password."""
    assert verify_password(PASSWORD, hash_password(PASSWORD)) is True


@pytest.mark.parametrize("attempt", ["wrong password", "", PASSWORD.upper(), PASSWORD + " "])
def test_wrong_password_is_rejected(attempt: str) -> None:
    """Fails if anything other than the exact password is accepted."""
    assert verify_password(attempt, hash_password(PASSWORD)) is False


def test_dummy_hash_is_a_real_argon2_hash_that_matches_no_password() -> None:
    """Fails if checking an unknown email could skip the slow Argon2 work (research R5)."""
    assert DUMMY_HASH.startswith("$argon2")
    assert verify_password(PASSWORD, DUMMY_HASH) is False
