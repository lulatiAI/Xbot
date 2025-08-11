import os
import time
import tweepy
import requests
from dotenv import load_dotenv
from fastapi import FastAPI

# --- Load environment variables ---
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")  # Correct usage
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL")

# --- Authenticate with X API ---
auth = tweepy.OAuth1UserHandler(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

BOT_ID = api.verify_credentials().id
BOT_HANDLE = api.me().screen_name.lower()

# Track last processed mention
last_seen_id_file = "last_seen_id.txt"

def retrieve_last_seen_id():
    try:
        with open(last_seen_id_file, "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        return None

def store_last_seen_id(last_seen_id):
    with open(last_seen_id_file, "w") as f:
        f.write(str(last_seen_id))

# --- Get AI-generated response ---
def get_ai_response(user_question):
    try:
        resp = requests.post(
            f"{AI_BACKEND_URL}/chat",
            json={"prompt": user_question},
            timeout=15
        )
        if resp.status_code == 200:
            return resp.json().get("response", "I’m not sure how to answer that right now.")
        else:
            return "Hmm, I’m having trouble thinking right now."
    except Exception as e:
        return f"Error: {e}"

# --- Process mentions ---
def reply_to_mentions():
    print("Checking for mentions...")
    last_seen_id = retrieve_last_seen_id()
    mentions = api.mentions_timeline(since_id=last_seen_id, tweet_mode="extended")

    for mention in reversed(mentions):
        print(f"Processing mention from @{men
