from app.rating_service import (
    calculate_expected_score,
    calculate_new_elo,
    calculate_trophy_change,
)


def test_equal_players_have_equal_expected_score():
    expected = calculate_expected_score(1000, 1000)

    assert expected == 0.5


def test_higher_rated_player_has_higher_expected_score():
    expected = calculate_expected_score(1200, 1000)

    assert expected > 0.5


def test_lower_rated_player_has_lower_expected_score():
    expected = calculate_expected_score(1000, 1200)

    assert expected < 0.5


def test_winner_gains_elo():
    new_rating = calculate_new_elo(
        player_elo=1000,
        opponent_elo=1000,
        won=True,
    )

    assert new_rating == 1016


def test_loser_loses_elo():
    new_rating = calculate_new_elo(
        player_elo=1000,
        opponent_elo=1000,
        won=False,
    )

    assert new_rating == 984


def test_winner_gets_trophy():
    new_trophy = calculate_trophy_change(
        current_trophy=1000,
        won=True,
    )

    assert new_trophy == 1025


def test_loser_loses_trophy():
    new_trophy = calculate_trophy_change(
        current_trophy=1000,
        won=False,
    )

    assert new_trophy == 975


def test_trophy_cannot_go_below_zero():
    new_trophy = calculate_trophy_change(
        current_trophy=10,
        won=False,
    )

    assert new_trophy == 0