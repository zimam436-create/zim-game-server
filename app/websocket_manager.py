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
        """
        Accept and register a player's WebSocket connection.

        If the player already has a connection, the new connection
        replaces the old one.
        """

        await websocket.accept()

        if match_id not in self.connections:
            self.connections[match_id] = {}

        self.connections[match_id][user_id] = websocket

    def disconnect(
        self,
        match_id: int,
        user_id: int,
        websocket: WebSocket | None = None,
    ):
        """
        Remove a player's WebSocket connection.

        If a specific websocket is supplied, only remove it if it is
        still the currently registered connection.

        This prevents an old connection from accidentally deleting
        a newer connection after the player reconnects.
        """

        if match_id not in self.connections:
            return

        current_websocket = self.connections[match_id].get(user_id)

        if current_websocket is None:
            return

        # If a specific socket was supplied, make sure we are
        # removing that exact socket and not a newer connection.
        if websocket is not None and current_websocket is not websocket:
            return

        self.connections[match_id].pop(user_id, None)

        if not self.connections[match_id]:
            del self.connections[match_id]

    def get_connection(
        self,
        match_id: int,
        user_id: int,
    ):
        """Return the player's active WebSocket."""

        return self.connections.get(match_id, {}).get(user_id)

    def get_players(
        self,
        match_id: int,
    ):
        """Return user IDs currently connected to the match."""

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
            # Only remove this socket if it is still the active one.
            self.disconnect(
                match_id,
                user_id,
                websocket,
            )

    async def broadcast(
        self,
        match_id: int,
        message: dict,
    ):
        """Send a JSON message to every connected player."""

        connections = self.connections.get(
            match_id,
            {},
        )

        # Make a copy so the dictionary can safely change
        # while broadcasting.
        players = list(connections.items())

        for user_id, websocket in players:
            try:
                await websocket.send_json(message)

            except Exception:
                # Only remove this specific socket.
                self.disconnect(
                    match_id,
                    user_id,
                    websocket,
                )


connection_manager = ConnectionManager()