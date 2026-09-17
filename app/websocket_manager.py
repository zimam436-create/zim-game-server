from fastapi import WebSocket


class ConnectionManager:
    """Manage active WebSocket connections for online matches."""

    def __init__(self):
        # match_id -> {user_id: WebSocket}
        self.connections: dict[int, dict[int, WebSocket]] = {}

    async def connect(
        self,
        match_id: int,
        user_id: int,
        websocket: WebSocket,
    ):
        """Accept and register a player's WebSocket connection."""

        await websocket.accept()

        if match_id not in self.connections:
            self.connections[match_id] = {}

        self.connections[match_id][user_id] = websocket

    def disconnect(
        self,
        match_id: int,
        user_id: int,
    ):
        """Remove a player's WebSocket connection."""

        if match_id not in self.connections:
            return

        self.connections[match_id].pop(user_id, None)

        if not self.connections[match_id]:
            del self.connections[match_id]

    def get_connection(
        self,
        match_id: int,
        user_id: int,
    ):
        """Return a player's active WebSocket connection."""

        return self.connections.get(match_id, {}).get(user_id)

    def get_players(
        self,
        match_id: int,
    ):
        """Return the user IDs currently connected to a match."""

        return list(
            self.connections.get(match_id, {}).keys()
        )

    async def send_to_player(
        self,
        match_id: int,
        user_id: int,
        message: dict,
    ):
        """Send a JSON message to one player."""

        websocket = self.get_connection(
            match_id,
            user_id,
        )

        if websocket is None:
            return

        try:
            await websocket.send_json(message)
        except Exception:
            # The socket may have disappeared between the lookup
            # and the send operation.
            self.disconnect(match_id, user_id)

    async def broadcast(
        self,
        match_id: int,
        message: dict,
    ):
        """Send a JSON message to every currently connected player."""

        connections = self.connections.get(match_id, {})

        # Make a copy so the dictionary can safely change if
        # a disconnected socket is removed during broadcasting.
        players = list(connections.items())

        for user_id, websocket in players:
            try:
                await websocket.send_json(message)
            except Exception:
                # One dead connection must not prevent the other
                # player from receiving the message.
                self.disconnect(match_id, user_id)


connection_manager = ConnectionManager()