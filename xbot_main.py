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
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
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
        print(f"Processing mention from @{mention.user.screen_name}: {mention.full_text}")
        
        # Skip if self-reply
        if mention.user.id == BOT_ID:
            continue

        # Clean up text: remove @botname
        user_question = mention.full_text.replace(f"@{BOT_HANDLE}", "").strip()

        # Only reply if it's a question
        if not user_question.endswith("?"):
            continue

        answer = get_ai_response(user_question)
        reply_text = f"@{mention.user.screen_name} {answer}"
        
        try:
            api.update_status(status=reply_text, in_reply_to_status_id=mention.id)
            print(f"Replied to @{mention.user.screen_name}")
        except Exception as e:
            print(f"Error replying: {e}")

        store_last_seen_id(mention.id)

# --- FastAPI health check endpoint ---
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "running", "bot": BOT_HANDLE}

# --- Background loop ---
if __name__ == "__main__":
    while True:
        reply_to_mentions()
        time.sleep(30)  # Check every 30 seconds
