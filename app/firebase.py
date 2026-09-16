from pathlib import Path

import firebase_admin
from firebase_admin import credentials, auth


BASE_DIR = Path(__file__).resolve().parent.parent
SERVICE_ACCOUNT_FILE = BASE_DIR / "zim-game-firebase-adminsdk-fbsvc-8554bbbc08.json"


if not firebase_admin._apps:
    cred = credentials.Certificate(str(SERVICE_ACCOUNT_FILE))
    firebase_admin.initialize_app(cred)


def verify_firebase_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return its decoded claims."""
    return auth.verify_id_token(id_token)