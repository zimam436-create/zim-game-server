import hashlib
import secrets

from pwdlib import PasswordHash


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2.
    """
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verify a password against an Argon2 hash.
    """
    return password_hash.verify(password, hashed_password)


def create_session_token() -> str:
    """
    Create a cryptographically secure random session token.
    """
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """
    Hash an opaque token before storing it in the database.
    """
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

def hash_session_token(token: str) -> str:
    """Hash a session token before storing it in the database."""
    return hash_token(token)


def create_password_reset_token() -> str:
    """Create a cryptographically secure, single-use password reset token."""
    return secrets.token_urlsafe(32)


def hash_password_reset_token(token: str) -> str:
    """Hash a password reset token before storing it in the database."""
    return hash_token(token)
