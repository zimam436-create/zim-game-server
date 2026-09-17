import asyncio
import json

import pytest
import websockets

from database.database import SessionLocal
from database.models import Match


SERVER_URL = "ws://127.0.0.1:8000"

PLAYER1_ID = 3
PLAYER2_ID = 5


async def connect_player(token: str, match_id: int):
    url = (
        f"{SERVER_URL}/ws/matches/"
        f"{match_id}?token={token}"
    )

    return await websockets.connect(url)


async def receive_until(websocket, message_type: str):
    while True:
        raw_message = await websocket.recv()
        message = json.loads(raw_message)

        if message.get("type") == message_type:
            return message


async def submit_choice(websocket, choice: str):
    await websocket.send(
        json.dumps(
            {
                "type": "choice",
                "choice": choice,
            }
        )
    )


async def play_round(
    player1,
    player2,
    player1_choice: str,
    player2_choice: str,
):
    await asyncio.gather(
        submit_choice(player1, player1_choice),
        submit_choice(player2, player2_choice),
    )

    await asyncio.gather(
        receive_until(player1, "choice_received"),
        receive_until(player2, "choice_received"),
    )

    result1, result2 = await asyncio.gather(
        receive_until(player1, "round_result"),
        receive_until(player2, "round_result"),
    )

    assert result1["round_number"] == result2["round_number"]
    assert result1["player1_choice"] == result2["player1_choice"]
    assert result1["player2_choice"] == result2["player2_choice"]
    assert result1["player1_score"] == result2["player1_score"]
    assert result1["player2_score"] == result2["player2_score"]
    assert result1["round_winner_id"] == result2["round_winner_id"]
    assert result1["match_finished"] == result2["match_finished"]
    assert result1["match_winner_id"] == result2["match_winner_id"]

    return result1, result2


def create_test_match():
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

        return match.id

    finally:
        db.close()


def delete_test_match(match_id: int):
    db = SessionLocal()

    try:
        match = (
            db.query(Match)
            .filter(Match.id == match_id)
            .first()
        )

        if match:
            db.delete(match)
            db.commit()

    finally:
        db.close()


@pytest.mark.asyncio
async def test_complete_multiplayer_match():
    """
    Test a complete first-to-5 multiplayer match.

    Player 1 = user 3
    Player 2 = user 5

    Player 1 should win 5-1.
    """

    match_id = create_test_match()

    player1 = None
    player2 = None

    try:

        with open(
            "player1_token.txt",
            "r",
            encoding="utf-8",
        ) as file:
            player1_token = file.read().strip()

        with open(
            "player2_token.txt",
            "r",
            encoding="utf-8",
        ) as file:
            player2_token = file.read().strip()

        player1 = await connect_player(
            player1_token,
            match_id,
        )

        player2 = await connect_player(
            player2_token,
            match_id,
        )

        await receive_until(
            player1,
            "connected",
        )

        await receive_until(
            player2,
            "connected",
        )

        await asyncio.gather(
            receive_until(player1, "match_ready"),
            receive_until(player2, "match_ready"),
        )

        # -----------------------------------------------------
        # Round 1
        # -----------------------------------------------------

        result1, result2 = await play_round(
            player1,
            player2,
            "rock",
            "scissors",
        )

        assert result1["round_number"] == 1
        assert result1["player1_score"] == 1
        assert result1["player2_score"] == 0
        assert result1["round_winner_id"] == PLAYER1_ID
        assert result1["match_finished"] is False

        await asyncio.gather(
            receive_until(player1, "next_round"),
            receive_until(player2, "next_round"),
        )

        # -----------------------------------------------------
        # Round 2
        # -----------------------------------------------------

        result1, result2 = await play_round(
            player1,
            player2,
            "paper",
            "rock",
        )

        assert result1["round_number"] == 2
        assert result1["player1_score"] == 2
        assert result1["player2_score"] == 0
        assert result1["round_winner_id"] == PLAYER1_ID
        assert result1["match_finished"] is False

        await asyncio.gather(
            receive_until(player1, "next_round"),
            receive_until(player2, "next_round"),
        )

        # -----------------------------------------------------
        # Round 3
        # -----------------------------------------------------

        result1, result2 = await play_round(
            player1,
            player2,
            "rock",
            "paper",
        )

        assert result1["round_number"] == 3
        assert result1["player1_score"] == 2
        assert result1["player2_score"] == 1
        assert result1["round_winner_id"] == PLAYER2_ID
        assert result1["match_finished"] is False

        await asyncio.gather(
            receive_until(player1, "next_round"),
            receive_until(player2, "next_round"),
        )

        # -----------------------------------------------------
        # Round 4
        # -----------------------------------------------------

        result1, result2 = await play_round(
            player1,
            player2,
            "scissors",
            "paper",
        )

        assert result1["round_number"] == 4
        assert result1["player1_score"] == 3
        assert result1["player2_score"] == 1
        assert result1["round_winner_id"] == PLAYER1_ID
        assert result1["match_finished"] is False

        await asyncio.gather(
            receive_until(player1, "next_round"),
            receive_until(player2, "next_round"),
        )

        # -----------------------------------------------------
        # Round 5
        # -----------------------------------------------------

        result1, result2 = await play_round(
            player1,
            player2,
            "paper",
            "rock",
        )

        assert result1["round_number"] == 5
        assert result1["player1_score"] == 4
        assert result1["player2_score"] == 1
        assert result1["round_winner_id"] == PLAYER1_ID
        assert result1["match_finished"] is False

        await asyncio.gather(
            receive_until(player1, "next_round"),
            receive_until(player2, "next_round"),
        )

        # -----------------------------------------------------
        # Round 6
        # -----------------------------------------------------

        result1, result2 = await play_round(
            player1,
            player2,
            "rock",
            "scissors",
        )

        assert result1["round_number"] == 6
        assert result1["player1_score"] == 5
        assert result1["player2_score"] == 1
        assert result1["round_winner_id"] == PLAYER1_ID
        assert result1["match_finished"] is True
        assert result1["match_winner_id"] == PLAYER1_ID

        # -----------------------------------------------------
        # Match finished message
        # -----------------------------------------------------

        finished1, finished2 = await asyncio.gather(
            receive_until(player1, "match_finished"),
            receive_until(player2, "match_finished"),
        )

        assert finished1["winner_id"] == PLAYER1_ID
        assert finished2["winner_id"] == PLAYER1_ID

        assert finished1["player1_score"] == 5
        assert finished1["player2_score"] == 1

        assert finished2["player1_score"] == 5
        assert finished2["player2_score"] == 1

    finally:

        if player1 is not None:
            await player1.close()

        if player2 is not None:
            await player2.close()

        delete_test_match(match_id)