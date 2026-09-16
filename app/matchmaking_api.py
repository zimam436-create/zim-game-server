from fastapi import APIRouter, Depends

from app.dependencies import get_verified_firebase_user
from app.matchmaking import matchmaking_queue
from database.models import User

router = APIRouter(
    prefix="/matchmaking",
    tags=["Matchmaking"],
)


@router.post("/join")
def join_matchmaking(
    current_user: User = Depends(get_verified_firebase_user),
):
    """Add the authenticated player to the matchmaking queue."""

    added = matchmaking_queue.add_player(current_user.id)

    if not added:
        return {
            "status": "already_waiting",
            "message": "You are already in the matchmaking queue.",
        }

    return {
        "status": "waiting",
        "message": "You have joined the matchmaking queue.",
        "user_id": current_user.id,
        "queue_size": matchmaking_queue.get_queue_size(),
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