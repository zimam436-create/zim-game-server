import asyncio
from dataclasses import dataclass
from threading import Lock
from typing import Awaitable, Callable

VALID_CHOICES = {"rock", "paper", "scissors"}

# How long a disconnected player has to reconnect.
RECONNECT_GRACE_PERIOD = 10


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

        # Protects all match-state transitions.
        self.lock = asyncio.Lock()

        # Current round state.
        self.current_round = RoundState(
            choices={},
            event=asyncio.Event(),
        )

        # user_id -> asyncio.Task
        #
        # A task exists while a player is inside the
        # reconnection grace period.
        self.reconnect_tasks: dict[int, asyncio.Task] = {}

        # Players whose connection is currently considered lost.
        self.disconnected_players: set[int] = set()

        # Players who have exceeded the reconnection period.
        self.forfeited_players: set[int] = set()
        # Called when a player fails to reconnect within
        # the grace period.
        self.forfeit_callback: Callable[[int], Awaitable[None]] | None = None

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
            # A disconnected/forfeited player must not be able
            # to submit choices.
            if user_id in self.forfeited_players:
                raise ValueError(
                    "You have forfeited this match."
                )

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
        for this round.

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

    def set_forfeit_callback(
        self,
        callback: Callable[[int], Awaitable[None]],
    ):
        """
        Register the callback that will run when a player
        fails to reconnect before the grace period expires.
        """

        self.forfeit_callback = callback

    async def mark_disconnected(self, user_id: int):
        """
        Mark a player as disconnected and start their
        reconnection grace period.

        Returns:
            True if the disconnect was registered.
            False if the player was already disconnected/forfeited.
        """

        if user_id not in (
            self.player1_id,
            self.player2_id,
        ):
            raise ValueError(
                "Player is not part of this match."
            )

        async with self.lock:
            if user_id in self.forfeited_players:
                return False

            # Ignore duplicate disconnect events.
            if user_id in self.disconnected_players:
                return False

            self.disconnected_players.add(user_id)

            # Cancel an existing timer if one somehow exists.
            existing_task = self.reconnect_tasks.pop(
                user_id,
                None,
            )

            if existing_task is not None:
                existing_task.cancel()

            # Start the 10-second reconnection timer.
            task = asyncio.create_task(
                self._reconnection_timeout(user_id)
            )

            self.reconnect_tasks[user_id] = task

            return True

    async def reconnect_player(self, user_id: int):
        """
        Reconnect a player during the grace period.

        The lock makes the reconnect-vs-forfeit race deterministic.

        If reconnection acquires the lock first, the player is
        restored and the timeout will not forfeit them.
        """

        if user_id not in (
            self.player1_id,
            self.player2_id,
        ):
            raise ValueError(
                "Player is not part of this match."
            )

        async with self.lock:
            # Player already forfeited.
            if user_id in self.forfeited_players:
                return False

            # Player wasn't disconnected.
            if user_id not in self.disconnected_players:
                return False

            # Remove disconnected status.
            self.disconnected_players.remove(user_id)

            # Cancel the pending timeout.
            task = self.reconnect_tasks.pop(
                user_id,
                None,
            )

            if task is not None:
                task.cancel()

            return True

    async def _reconnection_timeout(self, user_id: int):
        """
        Wait for the reconnection grace period.

        If the player is still disconnected after 10 seconds,
        mark them as forfeited and notify the WebSocket layer.

        The lock guarantees that reconnecting and forfeiting
        cannot happen simultaneously.
        """

        try:
            await asyncio.sleep(RECONNECT_GRACE_PERIOD)

            async with self.lock:
                # Player successfully reconnected.
                if user_id not in self.disconnected_players:
                    return

                self.disconnected_players.remove(user_id)

                self.forfeited_players.add(user_id)

                self.reconnect_tasks.pop(
                    user_id,
                    None,
                )

                callback = self.forfeit_callback

            # IMPORTANT:
            # Run the callback outside the lock.
            #
            # The callback may perform database and WebSocket
            # operations and must not block MatchState.
            if callback is not None:
                await callback(user_id)

        except asyncio.CancelledError:
            # Expected when the player reconnects before
            # the 10-second timer expires.
            return

    async def is_disconnected(self, user_id: int) -> bool:
        """
        Check whether a player is currently inside
        the reconnection grace period.
        """

        async with self.lock:
            return user_id in self.disconnected_players

    async def is_forfeited(self, user_id: int) -> bool:
        """
        Check whether a player has forfeited the match.
        """

        async with self.lock:
            return user_id in self.forfeited_players

    async def get_disconnected_players(self) -> set[int]:
        """
        Return a copy of the currently disconnected players.
        """

        async with self.lock:
            return set(self.disconnected_players)

    async def cleanup_reconnect_tasks(self):
        """
        Cancel all active reconnection timers.

        Used when the match is permanently removed.
        """

        async with self.lock:
            tasks = list(
                self.reconnect_tasks.values()
            )

            self.reconnect_tasks.clear()
            self.disconnected_players.clear()

            for task in tasks:
                task.cancel()


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

    async def remove_match(
        self,
        match_id: int,
    ):
        """
        Remove a match and cancel any outstanding
        reconnection timers.
        """

        with self.lock:
            state = self.matches.pop(
                match_id,
                None,
            )

        if state is not None:
            await state.cleanup_reconnect_tasks()

    def has_match(
        self,
        match_id: int,
    ) -> bool:

        with self.lock:
            return match_id in self.matches


match_state_manager = MatchStateManager()