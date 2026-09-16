import requests


API_KEY = "AIzaSyDhzcEq27GC6UrWN2352CuT6TAeL5QY4IU"

with open("firebase_test_token.txt", "r", encoding="utf-8") as file:
    token = file.read().strip()


url = (
    "https://identitytoolkit.googleapis.com/v1/"
    "accounts:sendOobCode"
)

response = requests.post(
    url,
    params={"key": API_KEY},
    json={
        "requestType": "VERIFY_EMAIL",
        "idToken": token,
    },
)

data = response.json()

if response.status_code != 200:
    print("Failed to send verification email:")
    print(data)
    raise SystemExit(1)

print("Verification email sent successfully!")