from fastapi import FastAPI
from sqlalchemy import text

from app.users import router as users_router
from database.database import engine

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi import Depends, FastAPI, HTTPException

from app.firebase import verify_firebase_token

from app.dependencies import get_verified_firebase_user
from database.models import User

app = FastAPI(
    title="Zim Game Server",
    version="2.0.0",
)

security = HTTPBearer()

app.include_router(users_router)


@app.get("/")
def root():
    return {
        "message": "Zim Game Server is running!",
        "version": "2.0.0",
    }


@app.get("/health")
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "status": "ok",
            "database": "connected",
        }


    except Exception as e:
        return {
            "status": "error",
            "database": "disconnected",
            "error": str(e),
        }

@app.get("/test/firebase")
def test_firebase(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    try:
        decoded_token = verify_firebase_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid Firebase ID token.",
        )

    return {
        "message": "Firebase authentication works!",
        "firebase_uid": decoded_token["uid"],
        "email": decoded_token.get("email"),
        "email_verified": decoded_token.get("email_verified", False),
    }

@app.get("/test/verified-user")
def test_verified_user(
    current_user: User = Depends(get_verified_firebase_user),
):
    return {
        "message": "Verified Firebase user accepted!",
        "username": current_user.username,
        "email": current_user.email,
        "email_verified": True,
    }
    