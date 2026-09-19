from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import (
    PlayerRating,
    PlayerStatistics,
    User,
)


def get_leaderboard(
    db: Session,
    limit: int = 50,
    offset: int = 0,
):
    """
    Return players ordered by trophy, Elo, and username.

    Rank is based only on trophy and Elo.
    Username is only a deterministic tie-breaker for display order.
    """

    rank_expression = func.rank().over(
        order_by=(
            PlayerRating.trophy.desc(),
            PlayerRating.elo_rating.desc(),
        )
    ).label("rank")

    rows = (
        db.query(
            rank_expression,
            User.id,
            User.username,
            PlayerRating.trophy,
            PlayerRating.elo_rating,
            PlayerStatistics.wins,
            PlayerStatistics.losses,
            PlayerStatistics.matches_played,
        )
        .join(
            PlayerRating,
            PlayerRating.user_id == User.id,
        )
        .join(
            PlayerStatistics,
            PlayerStatistics.user_id == User.id,
        )
        .order_by(
            PlayerRating.trophy.desc(),
            PlayerRating.elo_rating.desc(),
            User.username.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        {
            "rank": row.rank,
            "user_id": row.id,
            "username": row.username,
            "trophy": row.trophy,
            "elo_rating": row.elo_rating,
            "wins": row.wins,
            "losses": row.losses,
            "matches_played": row.matches_played,
        }
        for row in rows
    ]