from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_verified_firebase_user
from app.matchmaking import matchmaking_queue
from database.models import Match, User

router = APIRouter(
    prefix="/matchmaking",
    tags=["Matchmaking"],
)


@router.post("/join")
def join_matchmaking(
    current_user: User = Depends(get_verified_firebase_user),
    db: Session = Depends(get_db),
):
    """Add the player to matchmaking and create a match if possible."""

    added = matchmaking_queue.add_player(current_user.id)

    if not added:
        return {
            "status": "already_waiting",
            "message": "You are already in the matchmaking queue.",
        }

    match_players = matchmaking_queue.find_match()

    if match_players is None:
        return {
            "status": "waiting",
            "message": "You have joined the matchmaking queue.",
            "user_id": current_user.id,
            "queue_size": matchmaking_queue.get_queue_size(),
        }

    player1_id, player2_id = match_players

    match = Match(
        player1_id=player1_id,
        player2_id=player2_id,
        player1_score=0,
        player2_score=0,
        status="waiting",
    )

    db.add(match)
    db.commit()
    db.refresh(match)

    return {
        "status": "matched",
        "message": "Opponent found!",
        "match_id": match.id,
        "player1_id": player1_id,
        "player2_id": player2_id,
    }

@router.post("/leave")
def leave_matchmaking(
    current_user: User = Depends(get_verified_firebase_user),
):
    """Remove the authenticated player from the matchmaking queue."""

    removed = matchmaking_queue.remove_player(current_user.id)

    if not removed:
        return {
            "status": "not_waiting",
            "message": "You are not currently in the matchmaking queue.",
        }

    return {
        "status": "left",
        "message": "You have left the matchmaking queue.",
    }


@router.get("/status")
def matchmaking_status(
    current_user: User = Depends(get_verified_firebase_user),
):
    """Return the current matchmaking status."""

    return {
        "waiting": matchmaking_queue.is_waiting(current_user.id),
        "queue_size": matchmaking_queue.get_queue_size(),
    }