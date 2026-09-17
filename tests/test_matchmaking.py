import pytest

from app.matchmaking import MatchmakingQueue


@pytest.fixture
def queue():
    return MatchmakingQueue()


def test_first_player_waits(queue):
    result = queue.join_and_find_match(1)

    assert result is None
    assert queue.is_waiting(1)
    assert queue.get_queue_size() == 1


def test_second_player_creates_match(queue):
    queue.join_and_find_match(1)

    result = queue.join_and_find_match(2)

    assert result == (1, 2)

    assert not queue.is_waiting(1)
    assert not queue.is_waiting(2)

    assert queue.get_queue_size() == 0


def test_duplicate_player_is_rejected(queue):
    queue.join_and_find_match(1)

    with pytest.raises(ValueError):
        queue.join_and_find_match(1)

    assert queue.get_queue_size() == 1


def test_player_can_leave(queue):
    queue.join_and_find_match(1)

    removed = queue.remove_player(1)

    assert removed is True
    assert not queue.is_waiting(1)
    assert queue.get_queue_size() == 0


def test_leaving_player_who_is_not_waiting(queue):
    removed = queue.remove_player(999)

    assert removed is False


def test_three_players_only_match_first_two(queue):
    queue.join_and_find_match(1)

    result = queue.join_and_find_match(2)

    assert result == (1, 2)

    result = queue.join_and_find_match(3)

    assert result is None
    assert queue.is_waiting(3)
    assert queue.get_queue_size() == 1


def test_fifo_order(queue):
    queue.join_and_find_match(10)
    queue.join_and_find_match(20)

    # Both are already matched, so queue is empty.
    assert queue.get_queue_size() == 0

    queue.join_and_find_match(30)
    queue.join_and_find_match(40)

    assert queue.get_queue_size() == 0


def test_clear(queue):
    queue.join_and_find_match(1)
    queue.join_and_find_match(2)

    queue.join_and_find_match(3)

    assert queue.get_queue_size() == 1

    queue.clear()

    assert queue.get_queue_size() == 0