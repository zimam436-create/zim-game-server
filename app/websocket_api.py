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
async def match_websocket(
    websocket: WebSocket,
    match_id: int,
):
    """
    WebSocket endpoint for a real-time multiplayer match.

    Authentication:
        Firebase ID token is currently supplied through the
        WebSocket query parameter.

    Example:
        ws://127.0.0.1:8000/ws/matches/9?token=FIREBASE_ID_TOKEN
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

    # ---------------------------------------------------------
    # 3. Require verified email
    # ---------------------------------------------------------

    if not firebase_identity.get("email_verified", False):
        await websocket.close(code=1008)
        return

    firebase_uid = firebase_identity.get("uid")

    if not firebase_uid:
        await websocket.close(code=1008)
        return

    # ---------------------------------------------------------
    # 4. Find PostgreSQL user and match
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

        # Make sure this user actually belongs to this match.
        if user.id not in (
            match.player1_id,
            match.player2_id,
        ):
            await websocket.close(code=1008)
            return

        player1_id = match.player1_id
        player2_id = match.player2_id
        user_id = user.id

    finally:
        db.close()

    # ---------------------------------------------------------
    # 5. Get or create in-memory match state
    # ---------------------------------------------------------

    match_state = match_state_manager.get_or_create_match(
        match_id=match_id,
        player1_id=player1_id,
        player2_id=player2_id,
    )

    # ---------------------------------------------------------
    # 6. Register WebSocket connection
    # ---------------------------------------------------------

    await connection_manager.connect(
        match_id,
        user_id,
        websocket,
    )

    try:

        # -----------------------------------------------------
        # 7. Tell player that connection succeeded
        # -----------------------------------------------------

        await connection_manager.send_to_player(
            match_id,
            user_id,
            {
                "type": "connected",
                "match_id": match_id,
                "user_id": user_id,
                "message": "Connected to match.",
            },
        )

        # -----------------------------------------------------
        # 8. Check how many players are connected
        # -----------------------------------------------------

        players = connection_manager.get_players(match_id)

        if len(players) == 2:

            await connection_manager.broadcast(
                match_id,
                {
                    "type": "match_ready",
                    "match_id": match_id,
                    "message": (
                        "Both players are connected. "
                        "Round 1 starts now!"
                    ),
                },
            )

        else:

            await connection_manager.send_to_player(
                match_id,
                user_id,
                {
                    "type": "waiting_for_opponent",
                    "match_id": match_id,
                    "message": (
                        "Waiting for your opponent to connect..."
                    ),
                },
            )

        # -----------------------------------------------------
        # 9. Main WebSocket loop
        # -----------------------------------------------------

        while True:

            message = await websocket.receive_json()

            message_type = message.get("type")

            # =================================================
            # PLAYER CHOICE
            # =================================================

            if message_type == "choice":

                choice = message.get("choice")

                # -------------------------------------------------
                # Validate that choice is a string
                # -------------------------------------------------

                if not isinstance(choice, str):

                    await connection_manager.send_to_player(
                        match_id,
                        user_id,
                        {
                            "type": "error",
                            "message": (
                                "Choice must be a string."
                            ),
                        },
                    )

                    continue

                # -------------------------------------------------
                # Submit choice to MatchState
                # -------------------------------------------------

                try:

                    (
                        accepted,
                        should_process,
                        round_state,
                    ) = await match_state.submit_choice(
                        user_id=user_id,
                        choice=choice,
                    )

                except ValueError as error:

                    await connection_manager.send_to_player(
                        match_id,
                        user_id,
                        {
                            "type": "error",
                            "message": str(error),
                        },
                    )

                    continue

                # -------------------------------------------------
                # Duplicate choice
                # -------------------------------------------------

                if not accepted:

                    await connection_manager.send_to_player(
                        match_id,
                        user_id,
                        {
                            "type": "error",
                            "message": (
                                "You have already submitted "
                                "your choice for this round."
                            ),
                        },
                    )

                    continue

                # -------------------------------------------------
                # Tell player their choice was accepted
                # -------------------------------------------------

                await connection_manager.send_to_player(
                    match_id,
                    user_id,
                    {
                        "type": "choice_received",
                        "message": (
                            "Your choice has been received. "
                            "Waiting for your opponent..."
                        ),
                    },
                )

                # =================================================
                # CASE A:
                # This player is NOT responsible for processing
                # the round.
                # =================================================

                if not should_process:

                    # Wait for the exact round that this player
                    # just submitted a choice for.
                    result = (
                        await match_state.wait_for_round_result(
                            round_state
                        )
                    )

                    # The other handler is responsible for
                    # broadcasting the result.
                    #
                    # We do NOT broadcast here because that would
                    # cause duplicate round_result messages.
                    continue

                # =================================================
                # CASE B:
                # This player IS responsible for processing
                # the round.
                # =================================================
                # Get the choices belonging to this exact round.
                player1_choice, player2_choice = (
                    await match_state.get_choices(round_state)
                )

                # Safety check.
                #
                # If this happens, the other player's WebSocket may
                # already be waiting on this round's Event.
                #
                # Therefore we MUST finish/abort the round instead
                # of simply continuing.
                if (
                    player1_choice is None
                    or player2_choice is None
                ):
                    message = (
                        "Both player choices were not available."
                    )

                    await match_state.fail_round(
                        round_state=round_state,
                        message=message,
                    )

                    await connection_manager.broadcast(
                        match_id,
                        {
                            "type": "error",
                            "message": message,
                        },
                    )

                    continue

                db = SessionLocal()

                try:
                    # Load the match from PostgreSQL.
                    #
                    # PostgreSQL remains the source of truth.
                    match = (
                        db.query(Match)
                        .filter(Match.id == match_id)
                        .first()
                    )

                    if match is None:
                        message = "Match no longer exists."

                        await match_state.fail_round(
                            round_state=round_state,
                            message=message,
                        )

                        await connection_manager.broadcast(
                            match_id,
                            {
                                "type": "error",
                                "message": message,
                            },
                        )

                        continue

                    # The match may have been finished by another
                    # request or connection.
                    if match.status == "finished":
                        message = "This match has already finished."

                        await match_state.fail_round(
                            round_state=round_state,
                            message=message,
                        )

                        await connection_manager.broadcast(
                            match_id,
                            {
                                "type": "error",
                                "message": message,
                            },
                        )

                        continue

                    # Process the round.
                    #
                    # This updates PostgreSQL, calculates the winner,
                    # updates the match score, and may finish the match.
                    result = process_round(
                        db=db,
                        match=match,
                        player1_choice=player1_choice,
                        player2_choice=player2_choice,
                    )

                except Exception as error:
                    # IMPORTANT:
                    #
                    # The database operation may have failed.
                    # Roll back any partial transaction first.
                    db.rollback()

                    print(
                        f"Error processing round "
                        f"for match {match_id}: {error}"
                    )

                    message = (
                        "An error occurred while processing "
                        "the round."
                    )

                    # IMPORTANT:
                    #
                    # Wake the other WebSocket handler.
                    #
                    # Without this, the other player could remain
                    # blocked forever inside wait_for_round_result().
                    await match_state.fail_round(
                        round_state=round_state,
                        message=message,
                    )

                    await connection_manager.broadcast(
                        match_id,
                        {
                            "type": "error",
                            "message": message,
                        },
                    )

                    continue

                finally:
                    db.close()

                # The database operation succeeded.
                #
                # Store the result in this exact RoundState and wake
                # the other player's WebSocket handler.
                await match_state.finish_round(
                    round_state=round_state,
                    result=result,
                )

                # Send the round result to both players.
                await connection_manager.broadcast(
                    match_id,
                    {
                        "type": "round_result",
                        "round_number": result["round_number"],
                        "player1_choice": player1_choice,
                        "player2_choice": player2_choice,
                        "round_winner_id": result["round_winner_id"],
                        "player1_score": result["player1_score"],
                        "player2_score": result["player2_score"],
                        "match_finished": result["match_finished"],
                        "match_winner_id": result["match_winner_id"],
                    },
                )

                # If the match has finished, notify both players and
                # remove the temporary in-memory state.
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

                    await match_state_manager.remove_match(
                        match_id
                    )

                    break

                # Match continues.
                await connection_manager.broadcast(
                    match_id,
                    {
                        "type": "next_round",
                        "round_number": result["round_number"] + 1,
                    },
                )

            # =====================================================
            # UNKNOWN MESSAGE TYPE
            # =====================================================

            else:

                await connection_manager.send_to_player(
                    match_id,
                    user_id,
                    {
                        "type": "error",
                        "message": "Unknown message type.",
                    },
                )

    # =========================================================
    # PLAYER DISCONNECTED
    # =========================================================

    except WebSocketDisconnect:

        print(
            f"Player {user_id} disconnected "
            f"from match {match_id}."
        )

        connection_manager.disconnect(
            match_id,
            user_id,
        )
        # If nobody is connected anymore, discard the temporary
        # in-memory match state. PostgreSQL remains the source of truth.
        if not connection_manager.get_players(match_id):
            await match_state_manager.remove_match(match_id)

    except Exception as error:

        print(
            f"WebSocket error in match "
            f"{match_id}, player {user_id}: {error}"
        )

        connection_manager.disconnect(
            match_id,
            user_id,
        )
        # If nobody is connected anymore, discard the temporary
        # in-memory match state. PostgreSQL remains the source of truth.
        if not connection_manager.get_players(match_id):
            await match_state_manager.remove_match(match_id)
