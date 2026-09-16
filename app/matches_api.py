from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_verified_firebase_user
from app.match_service import process_round
from database.models import Match, User


router = APIRouter(
    prefix="/matches",
    tags=["Matches"],
)


class RoundRequest(BaseModel):
    choice: str


@router.post("/{match_id}/round")
def play_round(
    match_id: int,
    request: RoundRequest,
    current_user: User = Depends(get_verified_firebase_user),
    db: Session = Depends(get_db),
):
    """Submit a choice for a match round."""

    match = (
        db.query(Match)
        .filter(Match.id == match_id)
        .first()
    )

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found.",
        )

    if current_user.id not in (
        match.player1_id,
        match.player2_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a player in this match.",
        )

    if match.status == "finished":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This match has already finished.",
        )

    # For now, this endpoint is only a development/test endpoint.
    # It requires both choices in the request so we can test the
    # server-side game engine before implementing WebSockets.
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="WebSocket round handling will be implemented next.",
    )