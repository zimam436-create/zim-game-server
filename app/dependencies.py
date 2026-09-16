from collections.abc import Generator
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database.database import SessionLocal
from database.models import User

from app.firebase import verify_firebase_token


security = HTTPBearer()


def get_db() -> Generator:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()




def get_firebase_identity(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify a Firebase ID token and return its decoded identity."""

    try:
        decoded_token = verify_firebase_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase authentication token.",
        )

    if not decoded_token.get("uid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token does not contain a user ID.",
        )

    return decoded_token


def get_current_firebase_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate a request using a Firebase ID token."""

    try:
        decoded_token = verify_firebase_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase authentication token.",
        )

    firebase_uid = decoded_token.get("uid")

    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token does not contain a user ID.",
        )

    user = (
        db.query(User)
        .filter(User.firebase_uid == firebase_uid)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zim Game user account not found.",
        )

    return user


def get_verified_firebase_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate a Firebase user and require a verified email."""

    try:
        decoded_token = verify_firebase_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase authentication token.",
        )

    if not decoded_token.get("email_verified", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address must be verified.",
        )

    firebase_uid = decoded_token.get("uid")

    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token does not contain a user ID.",
        )

    user = (
        db.query(User)
        .filter(User.firebase_uid == firebase_uid)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zim Game user account not found.",
        )

    return user