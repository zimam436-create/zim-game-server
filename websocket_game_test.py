import asyncio
import json
from pathlib import Path

import websockets


MATCH_ID = 9
SERVER_URL = "ws://127.0.0.1:8000"


def load_token(filename):
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {filename}"
        )

    return path.read_text(encoding="utf-8").strip()


async def receive_until_round_result(name, websocket):
    """
    Keep receiving messages until the server sends
    the official round result.
    """

    while True:
        message = await websocket.recv()
        data = json.loads(message)

        message_type = data.get("type")

        if message_type == "connected":
            print(f"{name}: Connected.")

        elif message_type == "waiting_for_opponent":
            print(f"{name}: Waiting for opponent...")

        elif message_type == "match_ready":
            print(f"{name}: Match is ready!")

        elif message_type == "choice_received":
            print(f"{name}: Choice received by server.")

        elif message_type == "round_result":
            return data

        elif message_type == "error":
            print(f"{name}: SERVER ERROR → {data.get('message')}")

        else:
            print(f"{name}: {data}")


async def player(name, token, player_number):
    """
    Connect one player and play rounds until the match ends.
    """

    url = f"{SERVER_URL}/ws/matches/{MATCH_ID}?token={token}"

    print(f"\n{name}: Connecting...")

    async with websockets.connect(url) as websocket:

        # -----------------------------------------------------
        # Initial connection message
        # -----------------------------------------------------

        message = await websocket.recv()
        data = json.loads(message)

        print(f"{name}: {data.get('message')}")

        # -----------------------------------------------------
        # Keep listening for match-ready
        # -----------------------------------------------------

        while True:

            message = await websocket.recv()
            data = json.loads(message)

            message_type = data.get("type")

            if message_type == "waiting_for_opponent":
                print(f"{name}: Waiting for opponent...")
                continue

            if message_type == "match_ready":
                print(f"{name}: Both players connected!")
                break

            if message_type == "error":
                print(f"{name}: {data.get('message')}")

        # -----------------------------------------------------
        # Play rounds
        # -----------------------------------------------------

        while True:

            # ---------------------------------------------
            # Ask this player for a choice
            # ---------------------------------------------

            while True:

                choice = input(
                    f"\n{name} - Choose "
                    "(rock/paper/scissors): "
                ).strip().lower()

                if choice in {"rock", "paper", "scissors"}:
                    break

                print("Invalid choice. Try again.")

            # ---------------------------------------------
            # Send choice to server
            # ---------------------------------------------

            await websocket.send(
                json.dumps(
                    {
                        "type": "choice",
                        "choice": choice,
                    }
                )
            )

            print(f"{name}: Choice submitted.")

            # ---------------------------------------------
            # Wait for official result
            # ---------------------------------------------

            result = await receive_until_round_result(
                name,
                websocket,
            )

            # ---------------------------------------------
            # Display result
            # ---------------------------------------------

            print("\n" + "=" * 50)
            print(
                f"ROUND {result['round_number']} RESULT"
            )
            print("=" * 50)

            print(
                f"Player 1: "
                f"{result['player1_choice']}"
            )

            print(
                f"Player 2: "
                f"{result['player2_choice']}"
            )

            print(
                f"\nScore: "
                f"{result['player1_score']} - "
                f"{result['player2_score']}"
            )

            print(
                result["message"]
            )

            # ---------------------------------------------
            # Check whether match is finished
            # ---------------------------------------------

            if result["match_finished"]:

                print("\n" + "=" * 50)
                print("MATCH FINISHED")
                print("=" * 50)

                print(
                    f"Winner User ID: "
                    f"{result['match_winner_id']}"
                )

                print(
                    f"Final Score: "
                    f"{result['player1_score']} - "
                    f"{result['player2_score']}"
                )

                break

            # ---------------------------------------------
            # Wait for next-round message
            # ---------------------------------------------

            while True:

                message = await websocket.recv()
                data = json.loads(message)

                if data.get("type") == "next_round":
                    print(
                        f"{name}: Next round!"
                    )
                    break

                if data.get("type") == "error":
                    print(
                        f"{name}: "
                        f"{data.get('message')}"
                    )

        print(f"\n{name}: Match complete.")


async def main():

    player1_token = load_token(
        "player1_token.txt"
    )

    player2_token = load_token(
        "player2_token.txt"
    )

    print("=" * 50)
    print("ZIM GAME - FIRST TO 5 TEST")
    print("=" * 50)

    print(f"\nMatch ID: {MATCH_ID}")

    print(
        "\nPlayer 1 = User ID 5"
    )

    print(
        "Player 2 = User ID 3"
    )

    print(
        "\nOpen this script in TWO terminals "
        "if you want independent input."
    )

    print(
        "\nHowever, this test runs both players "
        "inside one program."
    )

    # ---------------------------------------------------------
    # Run both players simultaneously
    # ---------------------------------------------------------

    await asyncio.gather(
        player(
            "PLAYER 1",
            player1_token,
            1,
        ),
        player(
            "PLAYER 2",
            player2_token,
            2,
        ),
    )

    print("\nTest completed.")


if __name__ == "__main__":
    asyncio.run(main())