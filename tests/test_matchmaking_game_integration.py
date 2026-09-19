from fastapi.testclient import TestClient

from app.main import app
from app.matchmaking import matchmaking_queue
from app.matchmaking_websocket import matchmaking_connection_manager
from app.websocket_manager import connection_manager
from database.database import SessionLocal
from database.models import Match


def test_matchmaking_to_game_flow(monkeypatch):
    """
    Verify the complete flow:

    1. Player 1 connects to matchmaking.
    2. Player 2 connects to matchmaking.
    3. Both join the queue.
    4. The server creates a match.
    5. Both players receive the same match ID.
    6. Both players connect to the game WebSocket.
    7. Both players receive match_ready.
    8. Both submit choices.
    9. The server processes the round.
    10. Both players receive the same round result.
    """

    matchmaking_queue.clear()
    matchmaking_connection_manager.connections.clear()
    connection_manager.connections.clear()

    client = TestClient(app)

    player1_user_id = 5
    player2_user_id = 3

    token_map = {
        "player1-token": player1_user_id,
        "player2-token": player2_user_id,
    }

    db = SessionLocal()
    created_match_ids = []

    try:
        from database.models import User

        player1 = (
            db.query(User)
            .filter(User.id == player1_user_id)
            .one()
        )

        player2 = (
            db.query(User)
            .filter(User.id == player2_user_id)
            .one()
        )

        def fake_verify_token(token):
            user_id = token_map[token]

            if user_id == player1_user_id:
                firebase_uid = player1.firebase_uid
            else:
                firebase_uid = player2.firebase_uid

            return {
                "uid": firebase_uid,
                "email_verified": True,
            }

        monkeypatch.setattr(
            "app.matchmaking_websocket.verify_firebase_token",
            fake_verify_token,
        )

        monkeypatch.setattr(
            "app.websocket_api.verify_firebase_token",
            fake_verify_token,
        )

        # ---------------------------------------------------------
        # STEP 1: Player 1 joins matchmaking
        # ---------------------------------------------------------

        with client.websocket_connect(
            "/ws/matchmaking?token=player1-token"
        ) as matchmaking_ws1:

            connected1 = matchmaking_ws1.receive_json()

            assert connected1["type"] == "connected"
            assert connected1["user_id"] == player1_user_id

            matchmaking_ws1.send_json(
                {
                    "type": "join",
                }
            )

            searching = matchmaking_ws1.receive_json()

            assert searching["type"] == "searching"

            # -----------------------------------------------------
            # STEP 2: Player 2 joins matchmaking
            # -----------------------------------------------------

            with client.websocket_connect(
                "/ws/matchmaking?token=player2-token"
            ) as matchmaking_ws2:

                connected2 = matchmaking_ws2.receive_json()

                assert connected2["type"] == "connected"
                assert connected2["user_id"] == player2_user_id

                matchmaking_ws2.send_json(
                    {
                        "type": "join",
                    }
                )

                # Both players should receive match_found.
                match_found_2 = matchmaking_ws2.receive_json()
                match_found_1 = matchmaking_ws1.receive_json()

                assert match_found_1["type"] == "match_found"
                assert match_found_2["type"] == "match_found"

                assert (
                    match_found_1["match_id"]
                    == match_found_2["match_id"]
                )

                match_id = match_found_1["match_id"]

                created_match_ids.append(match_id)

                assert (
                    match_found_1["opponent_id"]
                    == player2_user_id
                )

                assert (
                    match_found_2["opponent_id"]
                    == player1_user_id
                )

                # -------------------------------------------------
                # STEP 3: Both players connect to the actual game
                # -------------------------------------------------

                with client.websocket_connect(
                    f"/ws/matches/{match_id}?token=player1-token"
                ) as game_ws1:

                    game_connected_1 = game_ws1.receive_json()

                    assert game_connected_1["type"] == "connected"
                    assert (
                        game_connected_1["user_id"]
                        == player1_user_id
                    )
                    assert (
                        game_connected_1["match_id"]
                        == match_id
                    )

                    # Player 1 connects first, so the server tells
                    # Player 1 to wait for the opponent.
                    waiting_1 = game_ws1.receive_json()

                    assert (
                        waiting_1["type"]
                        == "waiting_for_opponent"
                    )
                    assert waiting_1["match_id"] == match_id

                    # -------------------------------------------------
                    # Player 2 connects to the same match.
                    # -------------------------------------------------

                    with client.websocket_connect(
                        f"/ws/matches/{match_id}?token=player2-token"
                    ) as game_ws2:

                        game_connected_2 = game_ws2.receive_json()

                        assert game_connected_2["type"] == "connected"
                        assert (
                            game_connected_2["user_id"]
                            == player2_user_id
                        )
                        assert (
                            game_connected_2["match_id"]
                            == match_id
                        )

                        # When Player 2 connects, the server broadcasts
                        # match_ready to BOTH players.
                        ready_1 = game_ws1.receive_json()
                        ready_2 = game_ws2.receive_json()

                        assert ready_1["type"] == "match_ready"
                        assert ready_2["type"] == "match_ready"

                        assert ready_1["match_id"] == match_id
                        assert ready_2["match_id"] == match_id

                        # -------------------------------------------------
                        # STEP 4: Play one actual RPS round
                        # -------------------------------------------------

                        # Player 1 chooses rock.
                        game_ws1.send_json(
                            {
                                "type": "choice",
                                "choice": "rock",
                            }
                        )

                        # Player 1 should not receive the round result
                        # yet because Player 2 has not submitted a choice.

                        # Player 2 chooses scissors.
                        game_ws2.send_json(
                            {
                                "type": "choice",
                                "choice": "scissors",
                            }
                        )

                        # Both players should receive the round result.
                        round_result_1 = game_ws1.receive_json()
                        round_result_2 = game_ws2.receive_json()

                        assert (
                            round_result_1["type"]
                            == "round_result"
                        )

                        assert (
                            round_result_2["type"]
                            == "round_result"
                        )

                        assert (
                            round_result_1["round_number"]
                            == 1
                        )

                        assert (
                            round_result_2["round_number"]
                            == 1
                        )

                        # Player 1 chose rock.
                        # Player 2 chose scissors.
                        # Therefore Player 1 wins.
                        assert (
                            round_result_1["round_winner_id"]
                            == player1_user_id
                        )

                        assert (
                            round_result_2["round_winner_id"]
                            == player1_user_id
                        )

                        assert (
                            round_result_1["player1_score"]
                            == 1
                        )

                        assert (
                            round_result_1["player2_score"]
                            == 0
                        )

                        assert (
                            round_result_2["player1_score"]
                            == 1
                        )

                        assert (
                            round_result_2["player2_score"]
                            == 0
                        )

                        # One round is not enough to finish a
                        # first-to-5 match.
                        assert (
                            round_result_1["match_finished"]
                            is False
                        )

                        assert (
                            round_result_2["match_finished"]
                            is False
                        )

    finally:
        matchmaking_queue.clear()
        matchmaking_connection_manager.connections.clear()
        connection_manager.connections.clear()

        if created_match_ids:
            db.rollback()

            for match_id in created_match_ids:
                db.query(Match).filter(
                    Match.id == match_id
                ).delete(
                    synchronize_session=False
                )

            db.commit()

        db.close()