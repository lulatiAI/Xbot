import os
import time
import threading
import tweepy
import requests
from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

# --- API Keys ---
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")  # corrected name to match your env
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
last_seen_id = None  # could persist in a file/db

# --- Local city/state list ---
LOCAL_PLACES = [
    "chicago", "new york", "los angeles", "atlanta", "houston", "dallas",
    "miami", "washington", "north carolina", "south carolina", "detroit",
    "baltimore", "philadelphia", "new orleans", "oakland"
]

# --- Utility Functions ---
def get_news(query):
    """Fetch latest news headline matching query from News API."""
    try:
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}&pageSize=1&sortBy=publishedAt"
        r = requests.get(url)
        r.raise_for_status()
        articles = r.json().get("articles", [])
        if articles:
            return f"{articles[0]['title']} - {articles[0]['url']}"
        return None
    except Exception as e:
        print("Error fetching news:", e)
        return None

def get_ai_response(prompt):
    """Send prompt to AI backend for text response."""
    try:
        r = requests.post(f"{AI_BACKEND_URL}/generate-text", json={"prompt": prompt})
        r.raise_for_status()
        return r.json().get("response", "I couldn't process that.")
    except Exception as e:
        print("Error getting AI response:", e)
        return "Sorry, I had an error processing your request."

def process_mention(mention):
    """Process a mention and reply accordingly."""
    print(f"Processing mention from {mention.user.screen_name}: {mention.text}")
    lower_text = mention.text.lower()

    # Avoid replying to self
    if mention.user.id == BOT_ID:
        return

    # Check for local news
    for place in LOCAL_PLACES:
        if place in lower_text:
            news = get_news(place)
            if news:
                reply_text = f"@{mention.user.screen_name} Here's the latest news on {place}: {news}"
            else:
                reply_text = f"@{mention.user.screen_name} Couldn't find recent news for {place}."
            api.update_status(reply_text, in_reply_to_status_id=mention.id)
            return

    # General AI reply
    ai_reply = get_ai_response(lower_text)
    reply_text = f"@{mention.user.screen_name} {ai_reply}"
    api.update_status(reply_text, in_reply_to_status_id=mention.id)

def check_mentions():
    """Periodically check mentions."""
    global last_seen_id
    print("Checking mentions...")
    mentions = api.mentions_timeline(since_id=last_seen_id, tweet_mode="extended")
    for mention in reversed(mentions):
        last_seen_id = mention.id
        process_mention(mention)

# --- FastAPI app ---
app = FastAPI()

@app.get("/")
