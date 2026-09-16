VALID_CHOICES = {"rock", "paper", "scissors"}


def determine_round_winner(player1_choice: str, player2_choice: str):
    """
    Determine the winner of a Rock Paper Scissors round.

    Returns:
        1  -> Player 1 wins
        2  -> Player 2 wins
        0  -> Draw
    """

    player1_choice = player1_choice.lower().strip()
    player2_choice = player2_choice.lower().strip()

    if player1_choice not in VALID_CHOICES:
        raise ValueError("Invalid choice for player 1.")

    if player2_choice not in VALID_CHOICES:
        raise ValueError("Invalid choice for player 2.")

    if player1_choice == player2_choice:
        return 0

    winning_choices = {
        "rock": "scissors",
        "paper": "rock",
        "scissors": "paper",
    }

    if winning_choices[player1_choice] == player2_choice:
        return 1

    return 2


def has_match_winner(player1_score: int, player2_score: int) -> bool:
    """Return True when either player reaches 5 round wins."""

    return player1_score >= 5 or player2_score >= 5


def determine_match_winner(player1_score: int, player2_score: int):
    """
    Determine the overall match winner.

    Returns:
        1 -> Player 1 wins
        2 -> Player 2 wins
        None -> Match is not finished
    """

    if player1_score >= 5:
        return 1

    if player2_score >= 5:
        return 2

    return None