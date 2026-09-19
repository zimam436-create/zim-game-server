from database.database import SessionLocal
from database.models import PlayerRating, PlayerStatistics

from app.leaderboard import get_leaderboard


def test_leaderboard_returns_players_in_trophy_order():
    db = SessionLocal()

    try:
        player1_rating = (
            db.query(PlayerRating)
            .filter(PlayerRating.user_id == 5)
            .one()
        )

        player2_rating = (
            db.query(PlayerRating)
            .filter(PlayerRating.user_id == 3)
            .one()
        )

        original_player1_trophy = player1_rating.trophy
        original_player2_trophy = player2_rating.trophy

        player1_rating.trophy = 2000
        player2_rating.trophy = 1500

        db.commit()

        leaderboard = get_leaderboard(
            db=db,
            limit=10,
            offset=0,
        )

        player1 = next(
            player
            for player in leaderboard
            if player["user_id"] == 5
        )

        player2 = next(
            player
            for player in leaderboard
            if player["user_id"] == 3
        )

        assert player1["rank"] < player2["rank"]
        assert player1["trophy"] == 2000
        assert player2["trophy"] == 1500

    finally:
        player1_rating.trophy = original_player1_trophy
        player2_rating.trophy = original_player2_trophy
        db.commit()
        db.close()


def test_leaderboard_contains_required_fields():
    db = SessionLocal()

    try:
        leaderboard = get_leaderboard(
            db=db,
            limit=10,
            offset=0,
        )

        assert leaderboard

        required_fields = {
            "rank",
            "user_id",
            "username",
            "trophy",
            "elo_rating",
            "wins",
            "losses",
            "matches_played",
        }

        assert required_fields.issubset(
            leaderboard[0].keys()
        )

    finally:
        db.close()


def test_leaderboard_limit():
    db = SessionLocal()

    try:
        leaderboard = get_leaderboard(
            db=db,
            limit=1,
            offset=0,
        )

        assert len(leaderboard) <= 1

    finally:
        db.close()