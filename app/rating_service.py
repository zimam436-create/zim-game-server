DEFAULT_ELO = 1000
DEFAULT_TROPHY = 1000

ELO_K_FACTOR = 32
TROPHY_WIN = 25
TROPHY_LOSS = 25
MIN_TROPHY = 0


def calculate_expected_score(player_elo: int, opponent_elo: int) -> float:
    """
    Calculate the expected score for a player.

    Returns a value between 0 and 1.
    """
    return 1 / (
        1 + 10 ** ((opponent_elo - player_elo) / 400)
    )


def calculate_new_elo(
    player_elo: int,
    opponent_elo: int,
    won: bool,
) -> int:
    """
    Calculate a player's new Elo rating after a match.
    """
    expected_score = calculate_expected_score(
        player_elo,
        opponent_elo,
    )

    actual_score = 1.0 if won else 0.0

    new_rating = player_elo + ELO_K_FACTOR * (
        actual_score - expected_score
    )

    return round(new_rating)


def calculate_trophy_change(
    current_trophy: int,
    won: bool,
) -> int:
    """
    Calculate a player's new trophy value.
    """
    if won:
        return current_trophy + TROPHY_WIN

    return max(
        MIN_TROPHY,
        current_trophy - TROPHY_LOSS,
    )