import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")
ngrok_url = os.getenv("NGROK_URL")

# The user's phone number as requested
my_number = "+923146646856"

if not all([account_sid, auth_token, twilio_number, ngrok_url]):
    print("Error: Missing one or more required environment variables in .env")
    print("Ensure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, and NGROK_URL are set.")
    exit(1)

print(f"Connecting to Twilio with account SID: {account_sid[:5]}...")

client = Client(account_sid, auth_token)

# The webhook URL Twilio will request when the call connects
twiml_url = "https://handler.twilio.com/twiml/EH13b323821c099f11b71508f87660026f"

# Append a query parameter to automatically format http to https if ngrok_url failed
if not twiml_url.startswith("http"):
    twiml_url = f"https://{twiml_url}"

print(f"Initiating call from {twilio_number} to {my_number}")
print(f"Webhook URL for TwiML: {twiml_url}")

try:
    call = client.calls.create(
        to=my_number,
        from_=twilio_number,
        url=twiml_url,
        method="POST"
    )
    print(f"Call initiated successfully! Waiting for you to pick up.")
    print(f"Call SID: {call.sid}")
except Exception as e:
    print(f"Failed to initiate call. Error: {e}")
