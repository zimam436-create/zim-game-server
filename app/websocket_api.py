from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.firebase import verify_firebase_token
from app.match_state import match_state_manager
from app.match_service import process_round
from app.websocket_manager import connection_manager
from database.database import SessionLocal
from database.models import Match, User


router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/matches/{match_id}")
async def match_websocket(websocket: WebSocket, match_id: int):
    """
    WebSocket endpoint for real-time multiplayer matches.

    Development authentication:
        /ws/matches/{match_id}?token=FIREBASE_ID_TOKEN
    """

    # ---------------------------------------------------------
    # 1. Get Firebase token
    # ---------------------------------------------------------

    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=1008)
        return

    # ---------------------------------------------------------
    # 2. Verify Firebase token
    # ---------------------------------------------------------

    try:
        firebase_identity = verify_firebase_token(token)
    except Exception:
        await websocket.close(code=1008)
        return

    if not firebase_identity.get("email_verified", False):
        await websocket.close(code=1008)
        return

    firebase_uid = firebase_identity.get("uid")

    if not firebase_uid:
        await websocket.close(code=1008)
        return

    # ---------------------------------------------------------
    # 3. Find user and match in PostgreSQL
    # ---------------------------------------------------------

    db: Session = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.firebase_uid == firebase_uid)
            .first()
        )

        if not user:
            await websocket.close(code=1008)
            return

        match = (
            db.query(Match)
            .filter(Match.id == match_id)
            .first()
        )

        if not match:
            await websocket.close(code=1008)
            return

        # Make sure this user is actually one of the players.
        if user.id not in (match.player1_id, match.player2_id):
            await websocket.close(code=1008)
            return

        player1_id = match.player1_id
        player2_id = match.player2_id

    finally:
        db.close()

    # ---------------------------------------------------------
    # 4. Create/get server-side match state
    # ---------------------------------------------------------

    match_state = match_state_manager.get_match(match_id)

    if match_state is None:
        match_state = match_state_manager.create_match(
            match_id=match_id,
            player1_id=player1_id,
            player2_id=player2_id,
        )

    # ---------------------------------------------------------
    # 5. Connect WebSocket
    # ---------------------------------------------------------

    await connection_manager.connect(
        match_id,
        user.id,
        websocket,
    )

    try:

        # -----------------------------------------------------
        # 6. Tell player they connected
        # -----------------------------------------------------

        await connection_manager.send_to_player(
            match_id,
            user.id,
            {
                "type": "connected",
                "match_id": match_id,
                "user_id": user.id,
                "message": "Connected to match.",
            },
        )

        # -----------------------------------------------------
        # 7. Check whether both players are connected
        # -----------------------------------------------------

        players = connection_manager.get_players(match_id)

        if len(players) == 2:

            await connection_manager.broadcast(
                match_id,
                {
                    "type": "match_ready",
                    "match_id": match_id,
                    "message": "Both players are connected. Round 1 starts now!",
                },
            )

        else:

            await connection_manager.send_to_player(
                match_id,
                user.id,
                {
                    "type": "waiting_for_opponent",
                    "match_id": match_id,
                    "message": "Waiting for your opponent to connect...",
                },
            )

        # -----------------------------------------------------
        # 8. Main WebSocket loop
        # -----------------------------------------------------

        while True:

            message = await websocket.receive_json()

            message_type = message.get("type")

            # =================================================
            # PLAYER CHOICE
            # =================================================

            if message_type == "choice":

                choice = message.get("choice")

                if not isinstance(choice, str):
                    await connection_manager.send_to_player(
                        match_id,
                        user.id,
                        {
                            "type": "error",
                            "message": "Choice must be a string.",
                        },
                    )
                    continue

                try:

                    accepted = match_state.submit_choice(
                        user_id=user.id,
                        choice=choice,
                    )

                except ValueError as error:

                    await connection_manager.send_to_player(
                        match_id,
                        user.id,
                        {
                            "type": "error",
                            "message": str(error),
                        },
                    )

                    continue

                # Player already submitted this round.
                if not accepted:

                    await connection_manager.send_to_player(
                        match_id,
                        user.id,
                        {
                            "type": "error",
                            "message": "You have already submitted your choice for this round.",
                        },
                    )

                    continue

                # Do NOT reveal the choice to the opponent.
                await connection_manager.send_to_player(
                    match_id,
                    user.id,
                    {
                        "type": "choice_received",
                        "message": "Your choice has been received. Waiting for your opponent...",
                    },
                )

                # -------------------------------------------------
                # Wait until both players have chosen
                # -------------------------------------------------

                if not match_state.both_players_chose():
                    continue

                # -------------------------------------------------
                # Get both choices from server state
                # -------------------------------------------------

                player1_choice, player2_choice = match_state.get_choices()

                # -------------------------------------------------
                # Process official round in PostgreSQL
                # -------------------------------------------------

                db = SessionLocal()

                try:

                    match = (
                        db.query(Match)
                        .filter(Match.id == match_id)
                        .first()
                    )

                    if not match:
                        await connection_manager.broadcast(
                            match_id,
                            {
                                "type": "error",
                                "message": "Match no longer exists.",
                            },
                        )
                        break

                    result = process_round(
                        db=db,
                        match=match,
                        player1_choice=player1_choice,
                        player2_choice=player2_choice,
                    )

                except Exception:

                    db.rollback()

                    await connection_manager.broadcast(
                        match_id,
                        {
                            "type": "error",
                            "message": "An error occurred while processing the round.",
                        },
                    )

                    continue

                finally:
                    db.close()

                # -------------------------------------------------
                # Determine round winner
                # -------------------------------------------------

                round_winner_id = result["round_winner_id"]

                if round_winner_id == player1_id:
                    round_message = f"Player {player1_id} won the round!"

                elif round_winner_id == player2_id:
                    round_message = f"Player {player2_id} won the round!"

                else:
                    round_message = "The round was a draw!"

                # -------------------------------------------------
                # Broadcast official result
                # -------------------------------------------------

                await connection_manager.broadcast(
                    match_id,
                    {
                        "type": "round_result",
                        "round_number": result["round_number"],
                        "player1_choice": player1_choice,
                        "player2_choice": player2_choice,
                        "round_winner_id": round_winner_id,
                        "player1_score": result["player1_score"],
                        "player2_score": result["player2_score"],
                        "match_finished": result["match_finished"],
                        "match_winner_id": result["match_winner_id"],
                        "message": round_message,
                    },
                )

                # -------------------------------------------------
                # Match finished?
                # -------------------------------------------------

                if result["match_finished"]:

                    await connection_manager.broadcast(
                        match_id,
                        {
                            "type": "match_finished",
                            "match_id": match_id,
                            "winner_id": result["match_winner_id"],
                            "player1_score": result["player1_score"],
                            "player2_score": result["player2_score"],
                            "message": (
                                f"Player {result['match_winner_id']} "
                                f"won the match!"
                            ),
                        },
                    )

                    match_state_manager.remove_match(match_id)

                    break

                # -------------------------------------------------
                # Prepare for next round
                # -------------------------------------------------

                match_state.clear_choices()

                await connection_manager.broadcast(
                    match_id,
                    {
                        "type": "next_round",
                        "message": "Next round starts. Make your choice!",
                    },
                )

            # =================================================
            # UNKNOWN MESSAGE
            # =================================================

            else:

                await connection_manager.send_to_player(
                    match_id,
                    user.id,
                    {
                        "type": "error",
                        "message": "Unknown message type.",
                    },
                )

    except WebSocketDisconnect:

        connection_manager.disconnect(
            match_id,
            user.id,
        )