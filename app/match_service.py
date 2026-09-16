from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.game import (
    determine_match_winner,
    determine_round_winner,
)
from database.models import Match, MatchRound


def process_round(
    db: Session,
    match: Match,
    player1_choice: str,
    player2_choice: str,
):
    """
    Process one round of an RPS match.

    The database transaction updates both the round and the
    match score together.
    """

    if match.status == "finished":
        raise ValueError("This match has already finished.")

    # Determine the round winner using the game rules.
    round_result = determine_round_winner(
        player1_choice,
        player2_choice,
    )

    # Calculate the next round number.
    next_round = (
        db.query(MatchRound)
        .filter(MatchRound.match_id == match.id)
        .count()
        + 1
    )

    # Convert the game result into a user ID.
    if round_result == 1:
        round_winner_id = match.player1_id
        match.player1_score += 1

    elif round_result == 2:
        round_winner_id = match.player2_id
        match.player2_score += 1

    else:
        round_winner_id = None

    # Store the round.
    match_round = MatchRound(
        match_id=match.id,
        round_number=next_round,
        player1_choice=player1_choice.lower().strip(),
        player2_choice=player2_choice.lower().strip(),
        winner_id=round_winner_id,
    )

    db.add(match_round)

    # Check whether somebody has reached 5 wins.
    match_winner_result = determine_match_winner(
        match.player1_score,
        match.player2_score,
    )

    if match_winner_result == 1:
        match.winner_id = match.player1_id
        match.status = "finished"
        match.finished_at = datetime.now(timezone.utc)

    elif match_winner_result == 2:
        match.winner_id = match.player2_id
        match.status = "finished"
        match.finished_at = datetime.now(timezone.utc)

    # Commit the round and match update together.
    db.commit()

    # Refresh so we have the latest database state.
    db.refresh(match)

    return {
        "round_number": next_round,
        "round_winner_id": round_winner_id,
        "player1_score": match.player1_score,
        "player2_score": match.player2_score,
        "match_finished": match.status == "finished",
        "match_winner_id": match.winner_id,
    }