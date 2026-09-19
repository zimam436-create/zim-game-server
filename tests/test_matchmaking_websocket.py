import threading
import time

import pytest
import uvicorn
from fastapi.testclient import TestClient

from app.main import app
from app.matchmaking import matchmaking_queue
from app.matchmaking_websocket import (
    matchmaking_connection_manager,
)
from database.database import SessionLocal
from database.models import Match


def test_duplicate_join_is_rejected(monkeypatch):
    matchmaking_queue.clear()

    client = TestClient(app)

    player_id = 5

    def fake_verify_token(token):
        from database.database import SessionLocal
        from database.models import User

        db = SessionLocal()

        try:
            user = (
                db.query(User)
                .filter(User.id == player_id)
                .one()
            )

            return {
                "uid": user.firebase_uid,
                "email_verified": True,
            }

        finally:
            db.close()

    monkeypatch.setattr(
        "app.matchmaking_websocket.verify_firebase_token",
        fake_verify_token,
    )

    try:
        with client.websocket_connect(
            "/ws/matchmaking?token=player-token"
        ) as websocket:

            connected = websocket.receive_json()

            assert connected["type"] == "connected"

            websocket.send_json({"type": "join"})

            searching = websocket.receive_json()

            assert searching["type"] == "searching"

            websocket.send_json({"type": "join"})

            error = websocket.receive_json()

            assert error["type"] == "error"
            assert "already" in error["message"].lower()

    finally:
        matchmaking_queue.clear()
        matchmaking_connection_manager.connections.clear()


def test_leave_removes_player_from_queue(monkeypatch):
    matchmaking_queue.clear()

    client = TestClient(app)

    player_id = 5

    def fake_verify_token(token):
        from database.database import SessionLocal
        from database.models import User

        db = SessionLocal()

        try:
            user = (
                db.query(User)
                .filter(User.id == player_id)
                .one()
            )

            return {
                "uid": user.firebase_uid,
                "email_verified": True,
            }

        finally:
            db.close()

    monkeypatch.setattr(
        "app.matchmaking_websocket.verify_firebase_token",
        fake_verify_token,
    )

    try:
        with client.websocket_connect(
            "/ws/matchmaking?token=player-token"
        ) as websocket:

            websocket.receive_json()

            websocket.send_json({"type": "join"})

            searching = websocket.receive_json()

            assert searching["type"] == "searching"
            assert matchmaking_queue.is_waiting(player_id)

            websocket.send_json({"type": "leave"})

            response = websocket.receive_json()

            assert response["type"] == "left"
            assert response["removed"] is True
            assert not matchmaking_queue.is_waiting(player_id)

    finally:
        matchmaking_queue.clear()
        matchmaking_connection_manager.connections.clear()


def test_disconnect_removes_player_from_queue(monkeypatch):
    matchmaking_queue.clear()

    client = TestClient(app)

    player_id = 5

    def fake_verify_token(token):
        from database.database import SessionLocal
        from database.models import User

        db = SessionLocal()

        try:
            user = (
                db.query(User)
                .filter(User.id == player_id)
                .one()
            )

            return {
                "uid": user.firebase_uid,
                "email_verified": True,
            }

        finally:
            db.close()

    monkeypatch.setattr(
        "app.matchmaking_websocket.verify_firebase_token",
        fake_verify_token,
    )

    with client.websocket_connect(
        "/ws/matchmaking?token=player-token"
    ) as websocket:

        websocket.receive_json()

        websocket.send_json({"type": "join"})

        searching = websocket.receive_json()

        assert searching["type"] == "searching"
        assert matchmaking_queue.is_waiting(player_id)

    # Leaving the WebSocket context closes the connection.
    # The endpoint should remove the player from the queue.

    assert not matchmaking_queue.is_waiting(player_id)

    matchmaking_connection_manager.connections.clear()
    matchmaking_queue.clear()


def test_matchmaking_websocket_pairing(monkeypatch):
    """
    Verify that two authenticated players can connect to the
    matchmaking WebSocket, join the queue, and receive the same
    match ID.
    """

    matchmaking_queue.clear()

    client = TestClient(app)

    player1_user_id = 5
    player2_user_id = 3

    token_map = {
        "player1-token": player1_user_id,
        "player2-token": player2_user_id,
    }

    def fake_verify_token(token):
        user_id = token_map[token]

        return {
            "uid": f"test-firebase-uid-{user_id}",
            "email_verified": True,
        }

    monkeypatch.setattr(
        "app.matchmaking_websocket.verify_firebase_token",
        fake_verify_token,
    )

    db = SessionLocal()

    created_match_ids = []

    try:
        # Get Firebase UIDs from the existing test users.
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

        uid_map = {
            player1.firebase_uid: player1_user_id,
            player2.firebase_uid: player2_user_id,
        }

        def fake_verify_token(token):
            user_id = token_map[token]

            return {
                "uid": (
                    player1.firebase_uid
                    if user_id == player1_user_id
                    else player2.firebase_uid
                ),
                "email_verified": True,
            }

        monkeypatch.setattr(
            "app.matchmaking_websocket.verify_firebase_token",
            fake_verify_token,
        )

        with client.websocket_connect(
            "/ws/matchmaking?token=player1-token"
        ) as ws1:

            connected1 = ws1.receive_json()

            assert connected1["type"] == "connected"
            assert connected1["user_id"] == player1_user_id

            ws1.send_json({"type": "join"})

            searching = ws1.receive_json()

            assert searching["type"] == "searching"

            with client.websocket_connect(
                "/ws/matchmaking?token=player2-token"
            ) as ws2:

                connected2 = ws2.receive_json()

                assert connected2["type"] == "connected"
                assert connected2["user_id"] == player2_user_id

                ws2.send_json({"type": "join"})

                match_found_2 = ws2.receive_json()

                match_found_1 = ws1.receive_json()

                assert match_found_1["type"] == "match_found"
                assert match_found_2["type"] == "match_found"

                assert (
                    match_found_1["match_id"]
                    == match_found_2["match_id"]
                )

                match_id = match_found_1["match_id"]

                assert (
                    match_found_1["opponent_id"]
                    == player2_user_id
                )

                assert (
                    match_found_2["opponent_id"]
                    == player1_user_id
                )

                created_match_ids.append(match_id)

    finally:
        matchmaking_queue.clear()

        matchmaking_connection_manager.connections.clear()

        for match_id in created_match_ids:
            db.query(Match).filter(
                Match.id == match_id
            ).delete(
                synchronize_session=False
            )

        db.commit()
        db.close()