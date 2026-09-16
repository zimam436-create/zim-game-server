from threading import Lock


class MatchmakingQueue:
    """Thread-safe queue for players waiting for an online match."""

    def __init__(self):
        self._players = []
        self._lock = Lock()

    def add_player(self, user_id: int) -> bool:
        """
        Add a player to the matchmaking queue.

        Returns:
            True if the player was added.
            False if the player was already waiting.
        """
        with self._lock:
            if user_id in self._players:
                return False

            self._players.append(user_id)
            return True

    def remove_player(self, user_id: int) -> bool:
        """
        Remove a player from the queue.

        Returns:
            True if the player was removed.
            False if the player was not waiting.
        """
        with self._lock:
            if user_id not in self._players:
                return False

            self._players.remove(user_id)
            return True

    def find_match(self):
        """
        Take the first two players from the queue.

        Returns:
            A tuple containing two user IDs, or None
            if fewer than two players are waiting.
        """
        with self._lock:
            if len(self._players) < 2:
                return None

            player1 = self._players.pop(0)
            player2 = self._players.pop(0)

            return player1, player2

    def is_waiting(self, user_id: int) -> bool:
        """Check whether a player is currently waiting."""
        with self._lock:
            return user_id in self._players

    def get_queue_size(self) -> int:
        """Return the number of players currently waiting."""
        with self._lock:
            return len(self._players)


# One matchmaking queue for this server process.
matchmaking_queue = MatchmakingQueue()