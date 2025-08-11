import os
import time
import threading
import tweepy
import requests
from dotenv import load_dotenv
from fastapi import FastAPI

# Load environment variables from .env or deployment environment
load_dotenv()

# --- API Keys from environment ---
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

# --- Authenticate with Twitter/X API ---
auth = tweepy.OAuth1UserHandler(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

BOT_ID = api.verify_credentials().id
BOT_HANDLE = api.me().screen_name.lower()
last_seen_id = None  # Optional: persist in a file or DB

# --- Local city/state keywords ---
LOCAL_PLACES = [
    "chicago", "new york", "los angeles", "atlanta", "houston", "dallas",
    "miami", "washington", "north carolina", "south carolina", "detroit",
    "baltimore", "philadelphia", "new orleans", "oakland"
]

# --- Helper: Get news from NewsAPI ---
def get_news(query):
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}&language=en&pageSize=3"
    try:
        response = requests.get(url)
        data = response.json()
        if "articles" in data:
            return [
                f"{article['title']} - {article['url']}"
                for article in data["articles"]
            ]
    except Exception as e:
        print(f"Error fetching news: {e}")
    return []

# --- Helper: Call AI backend for a response ---
def call_ai_backend(prompt):
    try:
        resp = requests.post(
            AI_BACKEND_URL,
            json={"prompt": prompt},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json().get("response", "")
    except Exception as e:
        print(f"AI backend error: {e}")
    return "Sorry, I couldn’t process that right now."

# --- Bot Logic: Check mentions and reply ---
def check_mentions():
    global last_seen_id
    mentions = api.mentions_timeline(
        since_id=last_seen_id,
        tweet_mode="extended"
    )
    for mention in reversed(mentions):
        last_seen_id = mention.id
        text = mention.full_text.lower()
        user = mention.user.screen_name
        print(f"New mention from @{user}: {text}")

        # If user mentions a local place, fetch related news
        if any(place in text for place in LOCAL_PLACES):
            place = next(place for place in LOCAL_PLACES if place in text)
            news_items = get_news(place)
            if news_items:
                reply = f"Here are the latest updates for {place}:\n" + "\n".join(news_items)
            else:
                reply = f"Sorry, I couldn’t find any recent news for {place}."
        else:
            # Default: send text to AI backend
            reply = call_ai_backend(text)

        try:
            api.update_status(
                status=f"@{user} {reply}",
                in_reply_to_status_id=mention.id
            )
            print(f"Replied to @{user}")
        except Exception as e:
            print(f"Error replying to @{user}: {e}")

# --- Thread loop to keep checking mentions ---
def run_bot():
    while True:
        check_mentions()
        time.sleep(60)  # check every minute

# --- FastAPI app ---
app = FastAPI()

@app.get("/")
def home():
    return {"message": "X Bot is running"}

@app.post("/trigger-bot")
def trigger_bot():
    check_mentions()
    return {"status": "checked mentions"}

# --- Start bot in a separate thread ---
threading.Thread(target=run_bot, daemon=True).start()
