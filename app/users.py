import os
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import (
    get_current_firebase_user,
    get_db,
    get_firebase_identity,
)
from database.models import (
    PlayerRating,
    PlayerStatistics,
    User,
)


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


class RegisterRequest(BaseModel):
    username: str

class PasswordResetRequest(BaseModel):
    email: str

@router.post("/password-reset")
def request_password_reset(request: PasswordResetRequest):
    """Ask Firebase to send a password-reset email."""

    email = request.email.lower().strip()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is required.",
        )

    firebase_api_key = os.getenv("FIREBASE_WEB_API_KEY")

    if not firebase_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Firebase API key is not configured.",
        )

    url = (
        "https://identitytoolkit.googleapis.com/v1/"
        "accounts:sendOobCode"
    )

    response = requests.post(
        url,
        params={"key": firebase_api_key},
        json={
            "requestType": "PASSWORD_RESET",
            "email": email,
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to send password reset email.",
        )

    return {
        "message": "Password reset email sent successfully."
    }


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
)
def register(
    request: RegisterRequest,
    firebase_identity: dict = Depends(get_firebase_identity),
    db: Session = Depends(get_db),
):
    """
    Create a Zim Game profile for an authenticated Firebase user.

    Firebase is responsible for the user's email and password.
    PostgreSQL stores the Zim Game-specific profile.
    """

    firebase_uid = firebase_identity["uid"]
    email = firebase_identity.get("email")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase account does not contain an email address.",
        )

    email = email.lower().strip()
    username = request.username.strip()

    # Validate username.
    if len(username) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be at least 3 characters long.",
        )

    if len(username) > 32:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot exceed 32 characters.",
        )

    # Check whether this Firebase account already has a Zim Game profile.
    existing_firebase_user = (
        db.query(User)
        .filter(User.firebase_uid == firebase_uid)
        .first()
    )

    if existing_firebase_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Zim Game account already exists for this Firebase account.",
        )

    # Check username.
    existing_username = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already taken.",
        )

    # Check email.
    existing_email = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Create the Zim Game profile.
    user = User(
        username=username,
        email=email,
        firebase_uid=firebase_uid,
    )

    db.add(user)
    db.flush()

    # Create starting rating.
    rating = PlayerRating(
        user_id=user.id,
        trophy=1000,
        elo_rating=1000,
    )

    # Create starting statistics.
    statistics = PlayerStatistics(
        user_id=user.id,
        wins=0,
        losses=0,
        draws=0,
        matches_played=0,
    )

    db.add(rating)
    db.add(statistics)

    db.commit()
    db.refresh(user)

    return {
        "message": "Zim Game account created successfully.",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "firebase_uid": user.firebase_uid,
        },
    }


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_firebase_user),
):
    """Return the currently authenticated Zim Game user."""

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "firebase_uid": current_user.firebase_uid,
    }


@router.post("/password-reset")
def request_password_reset(request: PasswordResetRequest):
    """Ask Firebase to send a password-reset email."""

    email = request.email.lower().strip()

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is required.",
        )

    firebase_api_key = "YOUR_FIREBASE_WEB_API_KEY"

    url = (
        "https://identitytoolkit.googleapis.com/v1/"
        "accounts:sendOobCode"
    )

    response = requests.post(
        url,
        params={"key": firebase_api_key},
        json={
            "requestType": "PASSWORD_RESET",
            "email": email,
        },
        timeout=10,
    )

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to send password reset email.",
        )

    return {
        "message": "Password reset email sent successfully."
    }