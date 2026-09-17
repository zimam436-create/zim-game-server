from database.database import SessionLocal
from database.models import Match


# These IDs correspond to the users represented by:
#
# player1_token.txt -> user 3
# player2_token.txt -> user 5

PLAYER1_ID = 3
PLAYER2_ID = 5


def main():
    db = SessionLocal()

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

        print()
        print("======================================")
        print("TEST MATCH CREATED")
        print("======================================")
        print(f"Match ID:    {match.id}")
        print(f"Player 1:   user {match.player1_id}")
        print(f"Player 2:   user {match.player2_id}")
        print("======================================")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    main()