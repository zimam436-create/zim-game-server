import asyncio
from dataclasses import dataclass
from threading import Lock


VALID_CHOICES = {"rock", "paper", "scissors"}


@dataclass
class RoundState:
    """
    Holds all state belonging to one specific round.

    Each round gets its own Event so WebSocket handlers
    can wait for exactly that round to finish.
    """

    choices: dict[int, str]
    event: asyncio.Event
    result: dict | None = None
    processing: bool = False


class MatchState:
    def __init__(
        self,
        match_id: int,
        player1_id: int,
        player2_id: int,
    ):
        self.match_id = match_id
        self.player1_id = player1_id
        self.player2_id = player2_id

        # Protects state transitions.
        self.lock = asyncio.Lock()

        # Current round state.
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
                The RoundState object belonging to this round.
        """

        choice = choice.lower().strip()

        if choice not in VALID_CHOICES:
            raise ValueError(
                "Invalid choice. Choose rock, paper, or scissors."
            )

        if user_id not in (
            self.player1_id,
            self.player2_id,
        ):
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

            # Exactly one WebSocket handler becomes responsible
            # for processing the round.
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
        Finish a specific round and wake any handler waiting
        for that round.

        If the match continues, create a completely new
        RoundState for the next round.
        """

        async with self.lock:
            round_state.result = result
            round_state.processing = False

            # Keep a reference to this round's Event.
            completed_event = round_state.event

            # Clear the completed round's choices.
            round_state.choices.clear()

            # Wake the WebSocket handler waiting for this round.
            completed_event.set()

            # Create a fresh state for the next round.
            if not result.get("match_finished", False):
                self.current_round = RoundState(
                    choices={},
                    event=asyncio.Event(),
                )

    async def fail_round(
        self,
        round_state: RoundState,
        message: str,
    ):
        """
        Abort processing of a round safely.

        This is important because another WebSocket handler may
        already be waiting for this round's Event. It must never
        remain blocked forever because the database operation failed.
        """

        result = {
            "error": True,
            "message": message,
            "match_finished": False,
        }

        await self.finish_round(
            round_state=round_state,
            result=result,
        )

    async def get_choices(
        self,
        round_state: RoundState,
    ):
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

    def get_match(
        self,
        match_id: int,
    ):
        with self.lock:
            return self.matches.get(match_id)

    def remove_match(
        self,
        match_id: int,
    ):
        with self.lock:
            self.matches.pop(match_id, None)

    def has_match(
        self,
        match_id: int,
    ) -> bool:
        with self.lock:
            return match_id in self.matches


match_state_manager = MatchStateManager()