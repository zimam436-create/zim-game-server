from app.matchmaking import MatchmakingQueue


def test_add_player():
    queue = MatchmakingQueue()

    assert queue.add_player(1) is True
    assert queue.get_queue_size() == 1


def test_duplicate_player():
    queue = MatchmakingQueue()

    assert queue.add_player(1) is True
    assert queue.add_player(1) is False
    assert queue.get_queue_size() == 1


def test_remove_player():
    queue = MatchmakingQueue()

    queue.add_player(1)
    queue.add_player(2)

    assert queue.remove_player(1) is True
    assert queue.get_queue_size() == 1
    assert queue.is_waiting(1) is False


def test_find_match():
    queue = MatchmakingQueue()

    queue.add_player(1)
    queue.add_player(2)

    match = queue.find_match()

    assert match == (1, 2)
    assert queue.get_queue_size() == 0


def test_not_enough_players():
    queue = MatchmakingQueue()

    queue.add_player(1)

    assert queue.find_match() is None