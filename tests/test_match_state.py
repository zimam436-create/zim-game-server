import asyncio

import pytest

from app.match_state import (
    MatchState,
    MatchStateManager,
    RECONNECT_GRACE_PERIOD,
)


PLAYER1_ID = 3
PLAYER2_ID = 5
MATCH_ID = 9999


@pytest.mark.asyncio
async def test_player_can_disconnect():
    state = MatchState(
        match_id=MATCH_ID,
        player1_id=PLAYER1_ID,
        player2_id=PLAYER2_ID,
    )

    result = await state.mark_disconnected(PLAYER1_ID)

    assert result is True
    assert await state.is_disconnected(PLAYER1_ID) is True

    await state.cleanup_reconnect_tasks()


@pytest.mark.asyncio
async def test_player_can_reconnect_within_grace_period():
    state = MatchState(
        match_id=MATCH_ID,
        player1_id=PLAYER1_ID,
        player2_id=PLAYER2_ID,
    )

    await state.mark_disconnected(PLAYER1_ID)

    assert await state.is_disconnected(PLAYER1_ID) is True

    result = await state.reconnect_player(PLAYER1_ID)

    assert result is True
    assert await state.is_disconnected(PLAYER1_ID) is False
    assert await state.is_forfeited(PLAYER1_ID) is False

    await state.cleanup_reconnect_tasks()


@pytest.mark.asyncio
async def test_player_is_forfeited_after_grace_period():
    state = MatchState(
        match_id=MATCH_ID,
        player1_id=PLAYER1_ID,
        player2_id=PLAYER2_ID,
    )

    await state.mark_disconnected(PLAYER1_ID)

    await asyncio.sleep(RECONNECT_GRACE_PERIOD + 0.2)

    assert await state.is_disconnected(PLAYER1_ID) is False
    assert await state.is_forfeited(PLAYER1_ID) is True

    await state.cleanup_reconnect_tasks()


@pytest.mark.asyncio
async def test_reconnected_player_is_not_forfeited():
    state = MatchState(
        match_id=MATCH_ID,
        player1_id=PLAYER1_ID,
        player2_id=PLAYER2_ID,
    )

    await state.mark_disconnected(PLAYER1_ID)

    # Reconnect well before the 10-second timeout.
    await asyncio.sleep(0.1)

    result = await state.reconnect_player(PLAYER1_ID)

    assert result is True

    # Give the cancelled task a chance to finish.
    await asyncio.sleep(0.1)

    assert await state.is_disconnected(PLAYER1_ID) is False
    assert await state.is_forfeited(PLAYER1_ID) is False

    await state.cleanup_reconnect_tasks()


@pytest.mark.asyncio
async def test_forfeited_player_cannot_submit_choice():
    state = MatchState(
        match_id=MATCH_ID,
        player1_id=PLAYER1_ID,
        player2_id=PLAYER2_ID,
    )

    await state.mark_disconnected(PLAYER1_ID)

    await asyncio.sleep(RECONNECT_GRACE_PERIOD + 0.2)

    assert await state.is_forfeited(PLAYER1_ID) is True

    with pytest.raises(ValueError, match="forfeited"):
        await state.submit_choice(
            user_id=PLAYER1_ID,
            choice="rock",
        )

    await state.cleanup_reconnect_tasks()


@pytest.mark.asyncio
async def test_duplicate_disconnect_is_ignored():
    state = MatchState(
        match_id=MATCH_ID,
        player1_id=PLAYER1_ID,
        player2_id=PLAYER2_ID,
    )

    first_result = await state.mark_disconnected(PLAYER1_ID)
    second_result = await state.mark_disconnected(PLAYER1_ID)

    assert first_result is True
    assert second_result is False

    assert await state.is_disconnected(PLAYER1_ID) is True

    await state.cleanup_reconnect_tasks()


@pytest.mark.asyncio
async def test_reconnect_without_disconnect_is_ignored():
    state = MatchState(
        match_id=MATCH_ID,
        player1_id=PLAYER1_ID,
        player2_id=PLAYER2_ID,
    )

    result = await state.reconnect_player(PLAYER1_ID)

    assert result is False

    assert await state.is_disconnected(PLAYER1_ID) is False
    assert await state.is_forfeited(PLAYER1_ID) is False

    await state.cleanup_reconnect_tasks()


@pytest.mark.asyncio
async def test_match_cleanup_cancels_reconnection_timer():
    state = MatchState(
        match_id=MATCH_ID,
        player1_id=PLAYER1_ID,
        player2_id=PLAYER2_ID,
    )

    await state.mark_disconnected(PLAYER1_ID)

    assert await state.is_disconnected(PLAYER1_ID) is True

    await state.cleanup_reconnect_tasks()

    # The player should no longer be tracked as disconnected.
    assert await state.is_disconnected(PLAYER1_ID) is False

    # Wait briefly to make sure the cancelled timer does not
    # later mark the player as forfeited.
    await asyncio.sleep(0.2)

    assert await state.is_forfeited(PLAYER1_ID) is False


@pytest.mark.asyncio
async def test_both_players_can_have_independent_disconnect_timers():
    state = MatchState(
        match_id=MATCH_ID,
        player1_id=PLAYER1_ID,
        player2_id=PLAYER2_ID,
    )

    await state.mark_disconnected(PLAYER1_ID)
    await state.mark_disconnected(PLAYER2_ID)

    disconnected = await state.get_disconnected_players()

    assert disconnected == {
        PLAYER1_ID,
        PLAYER2_ID,
    }

    # Reconnect only Player 1.
    await state.reconnect_player(PLAYER1_ID)

    assert await state.is_disconnected(PLAYER1_ID) is False
    assert await state.is_disconnected(PLAYER2_ID) is True

    await state.cleanup_reconnect_tasks()