from threading import Lock


class MatchmakingQueue:
    """
    Thread-safe matchmaking queue.

    A player can appear in the queue only once.

    The important operation is join_and_find_match(), which
    adds a player and checks for a match atomically.
    """

    def __init__(self):
        self._players: list[int] = []
        self._lock = Lock()

    def join_and_find_match(self, user_id: int):
        """
        Add a player to the queue and immediately try to match
        them with another waiting player.

        Returns:
            None
                if the player is now waiting.

            (player1_id, player2_id)
                if two players were matched.

        Raises:
            ValueError
                if the player is already waiting.
        """

        with self._lock:

            if user_id in self._players:
                raise ValueError(
                    "You are already in the matchmaking queue."
                )

            self._players.append(user_id)

            if len(self._players) < 2:
                return None

            player1 = self._players.pop(0)
            player2 = self._players.pop(0)

            return player1, player2

    def add_player(self, user_id: int) -> bool:
        """
        Add a player without attempting to match them.

        Kept for simple queue-level operations and compatibility
        with existing code/tests.
        """

        with self._lock:

            if user_id in self._players:
                return False

            self._players.append(user_id)

            return True

    def remove_player(self, user_id: int) -> bool:
        """
        Remove a player from the queue.
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
            (player1_id, player2_id)

            or None if fewer than two players are waiting.
        """

        with self._lock:

            if len(self._players) < 2:
                return None

            player1 = self._players.pop(0)
            player2 = self._players.pop(0)

            return player1, player2

    def is_waiting(self, user_id: int) -> bool:
        """
        Check whether a player is currently waiting.
        """

        with self._lock:
            return user_id in self._players

    def get_queue_size(self) -> int:
        """
        Return the number of players currently waiting.
        """

        with self._lock:
            return len(self._players)

    def clear(self):
        """
        Empty the queue.

        Useful for tests and development.
        """

        with self._lock:
            self._players.clear()


matchmaking_queue = MatchmakingQueue()