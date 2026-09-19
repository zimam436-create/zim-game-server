from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.game import (
    determine_match_winner,
    determine_round_winner,
)
from app.rating_service import (
    calculate_new_elo,
    calculate_trophy_change,
)
from database.models import (
    Match,
    MatchRound,
    PlayerRating,
    PlayerStatistics,
)


def finish_match(
    db: Session,
    match: Match,
) -> None:
    """
    Finish a match and update both players' ratings and statistics.

    All changes are committed as one database transaction.
    """

    if match.status == "finished":
        raise ValueError("This match has already finished.")

    if match.winner_id is None:
        raise ValueError("Cannot finish a match without a winner.")

    player1_rating = (
        db.query(PlayerRating)
        .filter(PlayerRating.user_id == match.player1_id)
        .with_for_update()
        .one()
    )

    player2_rating = (
        db.query(PlayerRating)
        .filter(PlayerRating.user_id == match.player2_id)
        .with_for_update()
        .one()
    )

    player1_statistics = (
        db.query(PlayerStatistics)
        .filter(PlayerStatistics.user_id == match.player1_id)
        .with_for_update()
        .one()
    )

    player2_statistics = (
        db.query(PlayerStatistics)
        .filter(PlayerStatistics.user_id == match.player2_id)
        .with_for_update()
        .one()
    )

    player1_won = match.winner_id == match.player1_id
    player2_won = match.winner_id == match.player2_id

    player1_old_elo = player1_rating.elo_rating
    player2_old_elo = player2_rating.elo_rating

    player1_rating.elo_rating = calculate_new_elo(
        player_elo=player1_old_elo,
        opponent_elo=player2_old_elo,
        won=player1_won,
    )

    player2_rating.elo_rating = calculate_new_elo(
        player_elo=player2_old_elo,
        opponent_elo=player1_old_elo,
        won=player2_won,
    )

    player1_rating.trophy = calculate_trophy_change(
        current_trophy=player1_rating.trophy,
        won=player1_won,
    )

    player2_rating.trophy = calculate_trophy_change(
        current_trophy=player2_rating.trophy,
        won=player2_won,
    )

    now = datetime.now(timezone.utc)

    player1_rating.rating_updated_at = now
    player2_rating.rating_updated_at = now

    player1_statistics.matches_played += 1
    player2_statistics.matches_played += 1

    if player1_won:
        player1_statistics.wins += 1
        player2_statistics.losses += 1

    else:
        player2_statistics.wins += 1
        player1_statistics.losses += 1

    match.status = "finished"

    if match.finished_at is None:
        match.finished_at = now

    db.commit()


def process_round(
    db: Session,
    match: Match,
    player1_choice: str,
    player2_choice: str,
):
    """
    Process one round of an RPS match.

    The round and match score are persisted together.
    If the round finishes the match, the players' ratings
    and statistics are also updated.
    """

    if match.status == "finished":
        raise ValueError("This match has already finished.")

    round_result = determine_round_winner(
        player1_choice,
        player2_choice,
    )

    next_round = (
        db.query(MatchRound)
        .filter(MatchRound.match_id == match.id)
        .count()
        + 1
    )

    if round_result == 1:
        round_winner_id = match.player1_id
        match.player1_score += 1

    elif round_result == 2:
        round_winner_id = match.player2_id
        match.player2_score += 1

    else:
        round_winner_id = None

    match_round = MatchRound(
        match_id=match.id,
        round_number=next_round,
        player1_choice=player1_choice.lower().strip(),
        player2_choice=player2_choice.lower().strip(),
        winner_id=round_winner_id,
    )

    db.add(match_round)

    match_winner_result = determine_match_winner(
        match.player1_score,
        match.player2_score,
    )

    if match_winner_result == 1:
        match.winner_id = match.player1_id

        finish_match(
            db=db,
            match=match,
        )

    elif match_winner_result == 2:
        match.winner_id = match.player2_id

        finish_match(
            db=db,
            match=match,
        )

    else:
        db.commit()

    db.refresh(match)

    return {
        "round_number": next_round,
        "round_winner_id": round_winner_id,
        "player1_score": match.player1_score,
        "player2_score": match.player2_score,
        "match_finished": match.status == "finished",
        "match_winner_id": match.winner_id,
    }