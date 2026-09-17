import requests


API_KEY = "AIzaSyDhzcEq27GC6UrWN2352CuT6TAeL5QY4IU"


email = input("Firebase test email: ").strip()
password = input("Firebase test password: ")

output_file = input(
    "Token output filename (e.g. player1_token.txt): "
).strip()


url = (
    "https://identitytoolkit.googleapis.com/v1/"
    "accounts:signInWithPassword"
)


response = requests.post(
    url,
    params={"key": API_KEY},
    json={
        "email": email,
        "password": password,
        "returnSecureToken": True,
    },
)


data = response.json()


if response.status_code != 200:
    print("Firebase login failed:")
    print(data)
    raise SystemExit(1)


print("\nFirebase login successful!")
print("Firebase UID:", data["localId"])
print("ID token received successfully.")


with open(output_file, "w", encoding="utf-8") as file:
    file.write(data["idToken"])


print(f"\nID token saved to {output_file}")