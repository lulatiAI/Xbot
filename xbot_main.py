import os
import time
import threading
import tweepy
import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Load environment variables
load_dotenv()

# --- API Keys from environment variables ---
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")  # updated var name to match env
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

# --- Authenticate with X (Twitter) API ---
auth = tweepy.OAuth1UserHandler(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

BOT_ID = api.verify_credentials().id
BOT_HANDLE = api.me().screen_name.lower()
last_seen_id = None  # Could store this in a file/db for persistence

# --- Locations to track ---
LOCAL_PLACES = [
    "chicago", "new york", "los angeles", "atlanta", "houston", "dallas",
    "miami", "washington", "north carolina", "south carolina", "detroit",
    "baltimore", "philadelphia", "new orleans", "oakland"
]

# --- Fetch news articles ---
def get_news(query):
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}&language=en&pageSize=1"
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        if articles:
            return articles[0]["title"] + " - " + articles[0]["url"]
    return None

# --- Generate AI response from backend ---
def get_ai_response(prompt):
    try:
        response = requests.post(f"{AI_BACKEND_URL}/generate", json={"prompt": prompt})
        if response.status_code == 200:
            return response.json().get("response", "No response")
    except Exception as e:
        print(f"AI backend error: {e}")
    return "Error connecting to AI backend."

# --- Process mentions ---
def process_mentions():
    global last_seen_id
    mentions = api.mentions_timeline(since_id=last_seen_id, tweet_mode="extended")
    for mention in reversed(mentions):
        print(f"New mention from {mention.user.screen_name}: {mention.full_text}")
        last_seen_id = mention.id
        user_text = mention.full_text.replace(f"@{BOT_HANDLE}", "").strip()

        # Try to match with a local news place
        news_result = None
        for place in LOCAL_PLACES:
            if place in user_text.lower():
                news_result = get_news(place)
                break

        # AI reply if no local match
        if not news_result:
            news_result = get_ai_response(user_text)

        reply_text = f"@{mention.user.screen_name} {news_result or 'I could not find any info.'}"
        try:
            api.update_status(status=reply_text, in_reply_to_status_id=mention.id)
        except Exception as e:
            print(f"Error replying: {e}")

# --- Thread to continuously check mentions ---
def run_bot():
    while True:
        try:
            process_mentions()
        except Exception as e:
            print(f"Bot error: {e}")
        time.sleep(60)

# --- FastAPI app ---
app = FastAPI()

@app.get("/")
def home():
    return JSONResponse({"message": "X Bot is running."})

@app.post("/trigger-bot")
def trigger_bot():
    threading.Thread(target=process_mentions).start()
    return JSONResponse({"message": "Bot triggered."})

# --- Start bot on background thread ---
threading.Thread(target=run_bot, daemon=True).start()
