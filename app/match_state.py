from threading import Lock


class MatchState:
    def __init__(self, match_id: int, player1_id: int, player2_id: int):
        self.match_id = match_id
        self.player1_id = player1_id
        self.player2_id = player2_id

        # user_id -> submitted choice
        self.choices: dict[int, str] = {}

        self.lock = Lock()

    def submit_choice(self, user_id: int, choice: str) -> bool:
        """
        Store a player's choice for the current round.

        Returns True if the choice was accepted.
        Returns False if the player has already submitted.
        """

        choice = choice.lower().strip()

        if choice not in {"rock", "paper", "scissors"}:
            raise ValueError("Invalid choice.")

        if user_id not in (self.player1_id, self.player2_id):
            raise ValueError("Player is not part of this match.")

        with self.lock:
            if user_id in self.choices:
                return False

            self.choices[user_id] = choice
            return True

    def both_players_chose(self) -> bool:
        with self.lock:
            return (
                self.player1_id in self.choices
                and self.player2_id in self.choices
            )

    def get_choices(self):
        with self.lock:
            return (
                self.choices.get(self.player1_id),
                self.choices.get(self.player2_id),
            )

    def clear_choices(self):
        with self.lock:
            self.choices.clear()


class MatchStateManager:
    def __init__(self):
        # match_id -> MatchState
        self.matches: dict[int, MatchState] = {}
        self.lock = Lock()

    def create_match(
        self,
        match_id: int,
        player1_id: int,
        player2_id: int,
    ) -> MatchState:

        with self.lock:
            state = MatchState(
                match_id=match_id,
                player1_id=player1_id,
                player2_id=player2_id,
            )

            self.matches[match_id] = state

            return state

    def get_match(self, match_id: int):
        with self.lock:
            return self.matches.get(match_id)

    def remove_match(self, match_id: int):
        with self.lock:
            self.matches.pop(match_id, None)


match_state_manager = MatchStateManager()