import asyncio
from dataclasses import dataclass
from threading import Lock


VALID_CHOICES = {"rock", "paper", "scissors"}


@dataclass
class RoundState:
    """
    Holds all state belonging to one specific round.

    Each round gets its own Event, which allows both WebSocket
    handlers to wait for exactly this round to finish.
    """

    choices: dict[int, str]
    event: asyncio.Event
    result: dict | None = None
    processing: bool = False


class MatchState:
    def __init__(self, match_id: int, player1_id: int, player2_id: int):
        self.match_id = match_id
        self.player1_id = player1_id
        self.player2_id = player2_id

        # Protects state transitions inside this MatchState.
        self.lock = asyncio.Lock()

        # The current round.
        self.round_number = 1

        self.current_round = RoundState(
            choices={},
            event=asyncio.Event(),
        )

    async def submit_choice(
        self,
        user_id: int,
        choice: str,
    ):
        """
        Submit a player's choice for the current round.

        Returns:
            accepted:
                Whether the choice was accepted.

            should_process:
                True for exactly ONE player when both players
                have submitted their choices.

            round_state:
                The RoundState object for this round.
        """

        choice = choice.lower().strip()

        if choice not in VALID_CHOICES:
            raise ValueError(
                "Invalid choice. Choose rock, paper, or scissors."
            )

        if user_id not in (self.player1_id, self.player2_id):
            raise ValueError(
                "Player is not part of this match."
            )

        async with self.lock:
            round_state = self.current_round

            # Prevent duplicate submissions.
            if user_id in round_state.choices:
                return False, False, round_state

            # Store the choice.
            round_state.choices[user_id] = choice

            # If this is the second choice, exactly ONE
            # WebSocket handler becomes responsible for processing
            # the round.
            if (
                len(round_state.choices) == 2
                and not round_state.processing
            ):
                round_state.processing = True

                return True, True, round_state

            return True, False, round_state

    async def finish_round(
        self,
        round_state: RoundState,
        result: dict,
    ):
        """
        Mark a round as finished.

        The result is stored on the RoundState so the other
        WebSocket handler can retrieve the exact result belonging
        to the round it submitted its choice for.
        """

        async with self.lock:
            round_state.result = result
            round_state.processing = False

            # Save a reference to the event belonging specifically
            # to this round.
            completed_event = round_state.event

            # Clear the choices for the completed round.
            round_state.choices.clear()

            # Wake up the other player's WebSocket handler.
            completed_event.set()

            # If the match continues, create a completely new
            # RoundState for the next round.
            if not result.get("match_finished", False):
                self.round_number += 1

                self.current_round = RoundState(
                    choices={},
                    event=asyncio.Event(),
                )

    async def get_choices(self, round_state: RoundState):
        """
        Return the choices belonging to a specific round.
        """

        async with self.lock:
            return (
                round_state.choices.get(self.player1_id),
                round_state.choices.get(self.player2_id),
            )

    async def wait_for_round_result(
        self,
        round_state: RoundState,
    ):
        """
        Wait until this particular round has been processed.
        """

        await round_state.event.wait()

        return round_state.result


class MatchStateManager:
    def __init__(self):
        # match_id -> MatchState
        self.matches: dict[int, MatchState] = {}

        # Protects creation/removal of MatchState objects.
        self.lock = Lock()

    def create_match(
        self,
        match_id: int,
        player1_id: int,
        player2_id: int,
    ) -> MatchState:

        with self.lock:
            # Never accidentally overwrite an existing match state.
            existing = self.matches.get(match_id)

            if existing is not None:
                return existing

            state = MatchState(
                match_id=match_id,
                player1_id=player1_id,
                player2_id=player2_id,
            )

            self.matches[match_id] = state

            return state

    def get_or_create_match(
        self,
        match_id: int,
        player1_id: int,
        player2_id: int,
    ) -> MatchState:

        with self.lock:
            existing = self.matches.get(match_id)

            if existing is not None:
                return existing

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