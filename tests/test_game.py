import pytest

from app.game import (
    determine_match_winner,
    determine_round_winner,
    has_match_winner,
)


def test_rock_beats_scissors():
    assert determine_round_winner("rock", "scissors") == 1


def test_scissors_beats_paper():
    assert determine_round_winner("scissors", "paper") == 1


def test_paper_beats_rock():
    assert determine_round_winner("paper", "rock") == 1


def test_player2_wins():
    assert determine_round_winner("rock", "paper") == 2


def test_draw():
    assert determine_round_winner("rock", "rock") == 0


def test_uppercase_choices():
    assert determine_round_winner("ROCK", "scissors") == 1


def test_invalid_choice():
    with pytest.raises(ValueError):
        determine_round_winner("gun", "rock")


def test_match_not_finished():
    assert has_match_winner(4, 3) is False
    assert determine_match_winner(4, 3) is None


def test_player1_reaches_five():
    assert has_match_winner(5, 3) is True
    assert determine_match_winner(5, 3) == 1


def test_player2_reaches_five():
    assert has_match_winner(3, 5) is True
    assert determine_match_winner(3, 5) == 2