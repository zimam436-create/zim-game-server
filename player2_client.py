import asyncio
import json
from pathlib import Path

import websockets


MATCH_ID = 9
SERVER_URL = "ws://127.0.0.1:8000"

TOKEN_FILE = Path("player2_token.txt")
PLAYER_NAME = "PLAYER 2"


def load_token():
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            f"{TOKEN_FILE} was not found."
        )

    token = TOKEN_FILE.read_text(
        encoding="utf-8"
    ).strip()

    if not token:
        raise ValueError(
            f"{TOKEN_FILE} is empty."
        )

    return token


async def receive_messages(websocket):
    """
    Continuously receive messages from the server
    and display them.
    """

    try:
        async for message in websocket:
            print(f"\n[SERVER] {message}")

    except websockets.ConnectionClosed:
        print("\nConnection to server closed.")


async def game_loop(websocket):
    """
    Ask Player 2 for choices and send them to the server.
    """

    while True:

        choice = await asyncio.to_thread(
            input,
            "\nChoose rock, paper, scissors "
            "(or quit): ",
        )

        choice = choice.strip().lower()

        if choice == "quit":
            print("Leaving game...")
            await websocket.close()
            return

        if choice not in {
            "rock",
            "paper",
            "scissors",
        }:
            print(
                "Invalid choice. "
                "Choose rock, paper, or scissors."
            )
            continue

        await websocket.send(
            json.dumps(
                {
                    "type": "choice",
                    "choice": choice,
                }
            )
        )

        print(
            f"[{PLAYER_NAME}] Choice sent: {choice}"
        )


async def main():

    token = load_token()

    websocket_url = (
        f"{SERVER_URL}/ws/matches/"
        f"{MATCH_ID}?token={token}"
    )

    print("=" * 50)
    print(f"       {PLAYER_NAME} CLIENT")
    print("=" * 50)
    print(f"Match ID: {MATCH_ID}")
    print("Connecting to server...")
    print()

    try:

        async with websockets.connect(
            websocket_url
        ) as websocket:

            print(
                f"{PLAYER_NAME} connected successfully!"
            )

            receiver = asyncio.create_task(
                receive_messages(websocket)
            )

            try:
                await game_loop(websocket)

            finally:
                receiver.cancel()

    except Exception as error:

        print(
            f"\nConnection failed:\n{error}"
        )


if __name__ == "__main__":
    asyncio.run(main())