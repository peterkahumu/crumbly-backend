"""
Unit tests for the auth module — password hashing, JWT tokens.
"""

import pytest
from datetime import timedelta

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """Unit tests for bcrypt password hashing."""

    def test_hash_password_returns_string(self):
        hashed = hash_password("my-password")
        assert isinstance(hashed, str)
        assert hashed != "my-password"

    def test_verify_correct_password(self):
        hashed = hash_password("correct-horse")
        assert verify_password("correct-horse", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct-horse")
        assert verify_password("wrong-horse", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        # bcrypt produces different salts each time
        assert h1 != h2
        # But both verify correctly
        assert verify_password("same", h1)
        assert verify_password("same", h2)


class TestJWT:
    """Unit tests for JWT creation and verification."""

    def test_create_and_decode_token(self):
        token = create_access_token(data={"sub": "user-123", "role": "BAKER"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["role"] == "BAKER"
        assert "exp" in payload

    def test_create_token_with_custom_expiry(self):
        token = create_access_token(
            data={"sub": "user-456"},
            expires_delta=timedelta(minutes=5),
        )
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-456"

    def test_decode_invalid_token_returns_none(self):
        payload = decode_access_token("this.is.not.a.valid.jwt")
        assert payload is None

    def test_decode_empty_token_returns_none(self):
        payload = decode_access_token("")
        assert payload is None
