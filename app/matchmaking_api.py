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
    """
    Join the matchmaking queue.

    If another player is already waiting, create a match
    immediately.

    This endpoint is currently being used as our development
    matchmaking interface. Later, a matchmaking WebSocket will
    notify clients in real time when a match is found.
    """

    try:

        match_players = matchmaking_queue.join_and_find_match(
            current_user.id
        )

    except ValueError as error:

        return {
            "status": "already_waiting",
            "message": str(error),
        }

    # ---------------------------------------------------------
    # No opponent yet
    # ---------------------------------------------------------

    if match_players is None:

        return {
            "status": "waiting",
            "message": (
                "You have joined the matchmaking queue."
            ),
            "user_id": current_user.id,
            "queue_size": (
                matchmaking_queue.get_queue_size()
            ),
        }

    # ---------------------------------------------------------
    # Opponent found
    # ---------------------------------------------------------

    player1_id, player2_id = match_players

    match = Match(
        player1_id=player1_id,
        player2_id=player2_id,
        player1_score=0,
        player2_score=0,
        status="waiting",
    )

    try:

        db.add(match)
        db.commit()
        db.refresh(match)

    except Exception:

        db.rollback()

        # Important:
        # If database creation fails, put both players back
        # into the queue so they aren't silently lost.

        matchmaking_queue.add_player(player1_id)
        matchmaking_queue.add_player(player2_id)

        raise

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
    """
    Remove the authenticated player from matchmaking.
    """

    removed = matchmaking_queue.remove_player(
        current_user.id
    )

    if not removed:

        return {
            "status": "not_waiting",
            "message": (
                "You are not currently in "
                "the matchmaking queue."
            ),
        }

    return {
        "status": "left",
        "message": (
            "You have left the matchmaking queue."
        ),
    }


@router.get("/status")
def matchmaking_status(
    current_user: User = Depends(get_verified_firebase_user),
):
    """
    Return the authenticated player's matchmaking status.
    """

    return {
        "waiting": matchmaking_queue.is_waiting(
            current_user.id
        ),
        "queue_size": (
            matchmaking_queue.get_queue_size()
        ),
    }