import asyncio
import json
from pathlib import Path

import websockets


MATCH_ID = 1
SERVER_URL = "ws://127.0.0.1:8000"


def load_token(filename):
    path = Path(filename)

    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {filename}"
        )

    return path.read_text().strip()


async def player(name, token, choice):
    url = f"{SERVER_URL}/ws/matches/{MATCH_ID}?token={token}"

    print(f"\n{name}: Connecting...")

    async with websockets.connect(url) as websocket:

        # Receive initial server message
        message = await websocket.recv()

        print(f"{name} received:")
        print(json.dumps(json.loads(message), indent=2))

        # Send choice
        await websocket.send(
            json.dumps(
                {
                    "type": "choice",
                    "choice": choice,
                }
            )
        )

        print(f"{name}: Sent choice.")

        # Keep receiving messages
        try:
            while True:
                message = await websocket.recv()

                data = json.loads(message)

                print(f"\n{name} received:")
                print(json.dumps(data, indent=2))

                if data.get("type") == "match_finished":
                    break

                if data.get("type") == "round_result":
                    break

        except websockets.exceptions.ConnectionClosed:
            print(f"{name}: Connection closed.")


async def main():

    player1_token = load_token("player1_token.txt")
    player2_token = load_token("player2_token.txt")

    print("=" * 50)
    print("ZIM GAME - WEBSOCKET MATCH TEST")
    print("=" * 50)

    print("\nMatch ID:", MATCH_ID)

    # Change these choices to test different outcomes.
    player1_choice = "rock"
    player2_choice = "scissors"

    print("\nPlayer 1 choice:", player1_choice)
    print("Player 2 choice:", player2_choice)

    print("\nStarting both players...\n")

    await asyncio.gather(
        player(
            "PLAYER 1",
            player1_token,
            player1_choice,
        ),
        player(
            "PLAYER 2",
            player2_token,
            player2_choice,
        ),
    )

    print("\nTest completed.")


if __name__ == "__main__":
    asyncio.run(main())