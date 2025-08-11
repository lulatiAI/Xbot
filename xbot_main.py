import os
import time
import threading
import tweepy
import requests
from dotenv import load_dotenv
from fastapi import FastAPI

# Load environment variables from .env file (for local dev)
load_dotenv()

# --- API Keys & Config ---
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")  # Corrected name
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL")

if not all([API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_SECRET, NEWS_API_KEY, AI_BACKEND_URL]):
    raise ValueError("Missing one or more required environment variables.")

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

# --- FastAPI App ---
app = FastAPI()

@app.get("/")
def home():
    return {"message": "X Bot is running"}

# --- Utility Functions ---
def get_news(query):
    """Fetch latest news articles from NewsAPI for a given query."""
    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={query}&apiKey={NEWS_API_KEY}&language=en&sortBy=publishedAt&pageSize=3"
    )
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        articles = response.json().get("articles", [])
        return [
            f"{a['title']} - {a['url']}" for a in articles
            if a.get("title") and a.get("url")
        ]
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []

def generate_ai_response(prompt):
    """Send prompt to AI backend and return the generated text."""
    try:
        resp = requests.post(
            AI_BACKEND_URL,
            json={"prompt": prompt},
            timeout=20
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "No response from AI backend.")
    except Exception as e:
        print(f"Error contacting AI backend: {e}")
        return "Sorry, I couldn't process that request right now."

def reply_to_mentions():
    """Check mentions and reply with AI or news content."""
    global last_seen_id
    mentions = api.mentions_timeline(
        since_id=last_seen_id,
        tweet_mode="extended"
    )
    for mention in reversed(mentions):
        last_seen_id = mention.id
        user = mention.user.screen_name
        text = mention.full_text.lower()

        print(f"New mention from @{user}: {text}")

        if any(place in text for place in LOCAL_PLACES):
            # Fetch local news
            news_results = get_news(text)
            if news_results:
                reply = f"Here are the latest news updates:\n" + "\n".join(news_results)
            else:
                reply = "Sorry, I couldn't find any recent news for that location."
        else:
            # Generate AI response
            reply = generate_ai_response(text)

        try:
            api.update_status(
                status=f"@{user} {reply}",
                in_reply_to_status_id=mention.id
            )
        except Exception as e:
            print(f"Error replying to mention: {e}")

def run_bot_loop():
    """Background loop to keep checking mentions."""
    while True:
        try:
            reply_to_mentions()
        except Exception as e:
            print(f"Error in bot loop: {e}")
        time.sleep(60)  # check every 60 seconds

# Start the bot loop in a background thread
threading.Thread(target=run_bot_loop, daemon=True).start()
