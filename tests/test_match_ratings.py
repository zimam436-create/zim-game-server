from database.database import SessionLocal
from database.models import (
    Match,
    PlayerRating,
    PlayerStatistics,
)

from app.match_service import process_round


PLAYER1_ID = 5
PLAYER2_ID = 3


def play_round(db, match, player1_choice, player2_choice):
    return process_round(
        db=db,
        match=match,
        player1_choice=player1_choice,
        player2_choice=player2_choice,
    )


def test_match_winner_updates_rating_and_statistics():
    db = SessionLocal()

    match = None

    try:
        player1_rating = (
            db.query(PlayerRating)
            .filter(PlayerRating.user_id == PLAYER1_ID)
            .one()
        )

        player2_rating = (
            db.query(PlayerRating)
            .filter(PlayerRating.user_id == PLAYER2_ID)
            .one()
        )

        player1_statistics = (
            db.query(PlayerStatistics)
            .filter(PlayerStatistics.user_id == PLAYER1_ID)
            .one()
        )

        player2_statistics = (
            db.query(PlayerStatistics)
            .filter(PlayerStatistics.user_id == PLAYER2_ID)
            .one()
        )

        original_player1_elo = player1_rating.elo_rating
        original_player2_elo = player2_rating.elo_rating
        original_player1_trophy = player1_rating.trophy
        original_player2_trophy = player2_rating.trophy

        original_player1_wins = player1_statistics.wins
        original_player1_losses = player1_statistics.losses
        original_player1_matches = player1_statistics.matches_played

        original_player2_wins = player2_statistics.wins
        original_player2_losses = player2_statistics.losses
        original_player2_matches = player2_statistics.matches_played

        match = Match(
            player1_id=PLAYER1_ID,
            player2_id=PLAYER2_ID,
            player1_score=0,
            player2_score=0,
            status="waiting",
        )

        db.add(match)
        db.commit()
        db.refresh(match)

        # Player 1 wins 5-0.
        for _ in range(5):
            result = play_round(
                db,
                match,
                "rock",
                "scissors",
            )

        assert result["match_finished"] is True
        assert result["match_winner_id"] == PLAYER1_ID
        assert result["player1_score"] == 5
        assert result["player2_score"] == 0

        db.refresh(player1_rating)
        db.refresh(player2_rating)
        db.refresh(player1_statistics)
        db.refresh(player2_statistics)

        assert player1_rating.trophy == original_player1_trophy + 25
        assert player2_rating.trophy == original_player2_trophy - 25

        assert player1_rating.elo_rating > original_player1_elo
        assert player2_rating.elo_rating < original_player2_elo

        assert player1_statistics.wins == original_player1_wins + 1
        assert player1_statistics.losses == original_player1_losses
        assert player1_statistics.matches_played == original_player1_matches + 1

        assert player2_statistics.wins == original_player2_wins
        assert player2_statistics.losses == original_player2_losses + 1
        assert player2_statistics.matches_played == original_player2_matches + 1

    finally:
        if match is not None:
            db.query(Match).filter(Match.id == match.id).delete(
                synchronize_session=False
            )

        if "original_player1_elo" in locals():
            player1_rating.elo_rating = original_player1_elo
            player2_rating.elo_rating = original_player2_elo

            player1_rating.trophy = original_player1_trophy
            player2_rating.trophy = original_player2_trophy

            player1_statistics.wins = original_player1_wins
            player1_statistics.losses = original_player1_losses
            player1_statistics.matches_played = original_player1_matches

            player2_statistics.wins = original_player2_wins
            player2_statistics.losses = original_player2_losses
            player2_statistics.matches_played = original_player2_matches

        db.commit()
        db.close()


def test_player2_can_win_and_receive_rating_update():
    db = SessionLocal()

    match = None

    try:
        player1_rating = (
            db.query(PlayerRating)
            .filter(PlayerRating.user_id == PLAYER1_ID)
            .one()
        )

        player2_rating = (
            db.query(PlayerRating)
            .filter(PlayerRating.user_id == PLAYER2_ID)
            .one()
        )

        original_player1_elo = player1_rating.elo_rating
        original_player2_elo = player2_rating.elo_rating
        original_player1_trophy = player1_rating.trophy
        original_player2_trophy = player2_rating.trophy

        match = Match(
            player1_id=PLAYER1_ID,
            player2_id=PLAYER2_ID,
            player1_score=0,
            player2_score=0,
            status="waiting",
        )

        db.add(match)
        db.commit()
        db.refresh(match)

        # Player 2 wins 0-5.
        for _ in range(5):
            result = play_round(
                db,
                match,
                "scissors",
                "rock",
            )

        assert result["match_finished"] is True
        assert result["match_winner_id"] == PLAYER2_ID

        db.refresh(player1_rating)
        db.refresh(player2_rating)

        assert player1_rating.trophy == original_player1_trophy - 25
        assert player2_rating.trophy == original_player2_trophy + 25

        assert player1_rating.elo_rating < original_player1_elo
        assert player2_rating.elo_rating > original_player2_elo

    finally:
        if match is not None:
            db.query(Match).filter(Match.id == match.id).delete(
                synchronize_session=False
            )

        if "original_player1_elo" in locals():
            player1_rating.elo_rating = original_player1_elo
            player2_rating.elo_rating = original_player2_elo

            player1_rating.trophy = original_player1_trophy
            player2_rating.trophy = original_player2_trophy

        db.commit()
        db.close()


def test_finished_match_cannot_be_processed_again():
    db = SessionLocal()

    match = None

    try:
        match = Match(
            player1_id=PLAYER1_ID,
            player2_id=PLAYER2_ID,
            player1_score=0,
            player2_score=0,
            status="waiting",
        )

        db.add(match)
        db.commit()
        db.refresh(match)

        for _ in range(5):
            result = play_round(
                db,
                match,
                "rock",
                "scissors",
            )

        assert result["match_finished"] is True

        try:
            play_round(
                db,
                match,
                "rock",
                "scissors",
            )

            assert False, "Expected ValueError"

        except ValueError as exc:
            assert str(exc) == "This match has already finished."

    finally:
        if match is not None:
            db.query(Match).filter(Match.id == match.id).delete(
                synchronize_session=False
            )

        db.commit()
        db.close()