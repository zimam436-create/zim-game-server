from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import (
    get_db,
    get_verified_firebase_user,
)
from app.leaderboard import get_leaderboard
from database.models import User


router = APIRouter(
    prefix="/leaderboard",
    tags=["Leaderboard"],
)


@router.get("")
def leaderboard(
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    current_user: User = Depends(get_verified_firebase_user),
    db: Session = Depends(get_db),
):
    """
    Return the global player leaderboard.
    """

    return {
        "limit": limit,
        "offset": offset,
        "players": get_leaderboard(
            db=db,
            limit=limit,
            offset=offset,
        ),
    }