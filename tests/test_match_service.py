from database.database import SessionLocal
from database.models import Match

from app.match_service import process_round


def test_process_round():
    db = SessionLocal()

    try:
        # Use your existing users: 5 and 3.
        match = Match(
            player1_id=5,
            player2_id=3,
            player1_score=0,
            player2_score=0,
            status="waiting",
        )

        db.add(match)
        db.commit()
        db.refresh(match)

        match_id = match.id

        result = process_round(
            db=db,
            match=match,
            player1_choice="rock",
            player2_choice="scissors",
        )

        assert result["round_number"] == 1
        assert result["round_winner_id"] == 5
        assert result["player1_score"] == 1
        assert result["player2_score"] == 0
        assert result["match_finished"] is False

    finally:
        # Clean up the temporary match.
        db.query(Match).filter(Match.id == match_id).delete()
        db.commit()
        db.close()