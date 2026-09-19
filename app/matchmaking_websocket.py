from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.firebase import verify_firebase_token
from app.matchmaking import matchmaking_queue
from app.websocket_manager import connection_manager
from database.database import SessionLocal
from database.models import Match, User


router = APIRouter(tags=["Matchmaking WebSocket"])


class MatchmakingConnectionManager:
    """
    Manage WebSocket connections used specifically for matchmaking.

    user_id -> WebSocket
    """

    def __init__(self):
        self.connections: dict[int, WebSocket] = {}

    async def connect(
        self,
        user_id: int,
        websocket: WebSocket,
    ):
        """
        Accept and register a matchmaking connection.

        A newer connection replaces an older connection.
        """
        await websocket.accept()
        self.connections[user_id] = websocket

    def disconnect(
        self,
        user_id: int,
        websocket: WebSocket | None = None,
    ):
        """
        Remove a matchmaking connection.

        If a specific WebSocket is supplied, only remove it if
        it is still the currently registered connection.
        """
        current = self.connections.get(user_id)

        if current is None:
            return

        if websocket is not None and current is not websocket:
            return

        self.connections.pop(user_id, None)

    def get_connection(
        self,
        user_id: int,
    ):
        return self.connections.get(user_id)

    async def send_to_player(
        self,
        user_id: int,
        message: dict,
    ):
        websocket = self.get_connection(user_id)

        if websocket is None:
            return

        try:
            await websocket.send_json(message)

        except Exception:
            self.disconnect(
                user_id,
                websocket,
            )


matchmaking_connection_manager = MatchmakingConnectionManager()


async def create_match(
    player1_id: int,
    player2_id: int,
) -> Match:
    """
    Create a persistent Match for two matched players.
    """

    db: Session = SessionLocal()

    try:
        match = Match(
            player1_id=player1_id,
            player2_id=player2_id,
            player1_score=0,
            player2_score=0,
            status="waiting",
        )

        db.add(match)
        db.commit()
        db.refresh(match)

        return match

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


@router.websocket("/ws/matchmaking")
async def matchmaking_websocket(
    websocket: WebSocket,
):
    """
    Real-time matchmaking WebSocket.

    Authentication:
        Firebase ID token is currently supplied through
        the WebSocket query parameter.

    Example:
        ws://127.0.0.1:8000/ws/matchmaking?token=FIREBASE_ID_TOKEN
    """

    token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=1008)
        return

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

        user_id = user.id

    finally:
        db.close()

    await matchmaking_connection_manager.connect(
        user_id,
        websocket,
    )

    try:
        await matchmaking_connection_manager.send_to_player(
            user_id,
            {
                "type": "connected",
                "message": "Connected to matchmaking.",
                "user_id": user_id,
            },
        )

        while True:
            message = await websocket.receive_json()

            message_type = message.get("type")

            if message_type == "join":

                try:
                    match_players = matchmaking_queue.join_and_find_match(
                        user_id
                    )

                except ValueError as error:
                    await matchmaking_connection_manager.send_to_player(
                        user_id,
                        {
                            "type": "error",
                            "message": str(error),
                        },
                    )

                    continue

                if match_players is None:

                    await matchmaking_connection_manager.send_to_player(
                        user_id,
                        {
                            "type": "searching",
                            "message": "Searching for an opponent...",
                        },
                    )

                    continue

                player1_id, player2_id = match_players

                try:
                    match = await create_match(
                        player1_id,
                        player2_id,
                    )

                except Exception:
                    # Important:
                    # The players were removed from the queue before
                    # database creation. Put them back if creation fails.

                    matchmaking_queue.add_player(player1_id)
                    matchmaking_queue.add_player(player2_id)

                    await matchmaking_connection_manager.send_to_player(
                        user_id,
                        {
                            "type": "error",
                            "message": (
                                "Unable to create the match. "
                                "Please try again."
                            ),
                        },
                    )

                    continue

                await matchmaking_connection_manager.send_to_player(
                    player1_id,
                    {
                        "type": "match_found",
                        "match_id": match.id,
                        "opponent_id": player2_id,
                        "message": "Opponent found!",
                    },
                )

                await matchmaking_connection_manager.send_to_player(
                    player2_id,
                    {
                        "type": "match_found",
                        "match_id": match.id,
                        "opponent_id": player1_id,
                        "message": "Opponent found!",
                    },
                )

                continue

            if message_type == "leave":

                removed = matchmaking_queue.remove_player(
                    user_id
                )

                await matchmaking_connection_manager.send_to_player(
                    user_id,
                    {
                        "type": "left",
                        "removed": removed,
                        "message": (
                            "You left matchmaking."
                            if removed
                            else "You were not waiting for an opponent."
                        ),
                    },
                )

                continue

            if message_type == "status":

                await matchmaking_connection_manager.send_to_player(
                    user_id,
                    {
                        "type": "status",
                        "waiting": matchmaking_queue.is_waiting(
                            user_id
                        ),
                        "queue_size": matchmaking_queue.get_queue_size(),
                    },
                )

                continue

            await matchmaking_connection_manager.send_to_player(
                user_id,
                {
                    "type": "error",
                    "message": "Unknown matchmaking message type.",
                },
            )

    except WebSocketDisconnect:

        # If the player disconnects while waiting,
        # remove them from the matchmaking queue.
        matchmaking_queue.remove_player(user_id)

        matchmaking_connection_manager.disconnect(
            user_id,
            websocket,
        )

    except Exception as error:

        print(
            f"Matchmaking WebSocket error "
            f"for player {user_id}: {error}"
        )

        matchmaking_queue.remove_player(user_id)

        matchmaking_connection_manager.disconnect(
            user_id,
            websocket,
        )