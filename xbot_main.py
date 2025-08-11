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
API_KEY_SECRET = os.getenv("API_KEY_SECRET")  # fixed name
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL")

# --- Authenticate with X (Twitter) API ---
auth = tweepy.OAuth1UserHandler(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

BOT_ID = api.verify_credentials().id
BOT_HANDLE = api.me().screen_name.lower()
last_seen_id = None  # This could be persisted in a file if needed

# --- Local city/state list ---
LOCAL_PLACES = [
    "chicago", "new york", "los angeles", "atlanta", "houston", "dallas",
    "miami", "washington", "north carolina", "south carolina", "detroit",
    "baltimore", "philadelphia", "new orleans", "oakland"
]

# --- Utility Functions ---
def get_news(query):
    """Fetch latest news headlines from NewsAPI."""
    url = f"https://newsapi.org/v2/everything?q={query}&sortBy=publishedAt&apiKey={NEWS_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if "articles" in data:
            return [article["title"] for article in data["articles"][:3]]
    except Exception as e:
        print(f"Error fetching news: {e}")
    return []

def ask_ai(prompt):
    """Send a prompt to the AI backend and return its response."""
    if not AI_BACKEND_URL:
        return "AI backend URL not configured."
    try:
        response = requests.post(
            f"{AI_BACKEND_URL}/generate",
            json={"prompt": prompt},
            timeout=15
        )
        return response.json().get("response", "No response from AI.")
    except Exception as e:
        return f"Error contacting AI backend: {e}"

def reply_to_mentions():
    """Check mentions and reply with AI-generated answers or news."""
    global last_seen_id
    try:
        mentions = api.mentions_timeline(
            since_id=last_seen_id,
            tweet_mode="extended"
        )
        for mention in reversed(mentions):
            print(f"Processing mention from {mention.user.screen_name}: {mention.full_text}")
            last_seen_id = mention.id

            user_text = mention.full_text.lower()
            reply_text = ""

            if any(city in user_text for city in LOCAL_PLACES):
                city = next(city for city in LOCAL_PLACES if city in user_text)
                headlines = get_news(city)
                reply_text = f"Top news in {city.title()}:\n- " + "\n- ".join(headlines) if headlines else f"No recent news for {city}."
            else:
                reply_text = ask_ai(user_text)

            if reply_text:
                api.update_status(
                    status=f"@{mention.user.screen_name} {reply_text}",
                    in_reply_to_status_id=mention.id
                )
    except Exception as e:
        print(f"Error replying to mentions: {e}")

# --- Background Thread ---
def run_bot():
    while True:
        reply_to_mentions()
        time.sleep(60)

# --- FastAPI App ---
app = FastAPI()

@app.get("/")
def home():
    return {"message": f"XBot running as @{BOT_HANDLE}"}

@app.post("/trigger")
def trigger_bot():
    reply_to_mentions()
    return {"status": "Mentions processed"}

# Start bot in background thread
threading.Thread(target=run_bot, daemon=True).start()
