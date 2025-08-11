import os
import time
import threading
import tweepy
import requests
from dotenv import load_dotenv
from fastapi import FastAPI

# Load environment variables from .env (optional if hosting sets them)
load_dotenv()

# --- Environment Variables ---
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")  # Correct variable name
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL")

if not all([API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_SECRET]):
    raise ValueError("Twitter API credentials are missing in environment variables!")

if not NEWS_API_KEY:
    print("⚠️ WARNING: No NEWS_API_KEY found. News feature will be disabled.")

if not AI_BACKEND_URL:
    print("⚠️ WARNING: No AI_BACKEND_URL found. AI responses will be disabled.")

# --- Authenticate with X (Twitter) API ---
auth = tweepy.OAuth1UserHandler(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

BOT_ID = api.verify_credentials().id
BOT_HANDLE = api.me().screen_name.lower()
last_seen_id = None

# --- Places to watch for in tweets ---
LOCAL_PLACES = [
    "chicago", "new york", "los angeles", "atlanta", "houston", "dallas",
    "miami", "washington", "north carolina", "south carolina", "detroit",
    "baltimore", "philadelphia", "new orleans", "oakland"
]

# --- Get News Function ---
def get_news(query):
    if not NEWS_API_KEY:
        return "News API not configured."
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={NEWS_API_KEY}&pageSize=1&sortBy=publishedAt"
    response = requests.get(url)
    if response.status_code == 200:
        articles = response.json().get("articles", [])
        if articles:
            article = articles[0]
            return f"{article['title']} - {article['url']}"
    return "No news found."

# --- Get AI Response ---
def get_ai_response(prompt):
    if not AI_BACKEND_URL:
        return "AI backend not configured."
    try:
        res = requests.post(f"{AI_BACKEND_URL}/generate", json={"prompt": prompt}, timeout=30)
        if res.status_code == 200:
            return res.json().get("response", "No response from AI.")
        else:
            return f"Error: {res.status_code} from AI backend."
    except Exception as e:
        return f"AI request failed: {e}"

# --- Process Mentions ---
def process_mentions():
    global last_seen_id
    print("🔍 Checking mentions...")
    mentions = api.mentions_timeline(since_id=last_seen_id, tweet_mode="extended")
    for mention in reversed(mentions):
        print(f"📌 Mention from @{mention.user.screen_name}: {mention.full_text}")
        last_seen_id = mention.id

        text = mention.full_text.lower().replace(f"@{BOT_HANDLE}", "").strip()

        reply_text = None
        if any(place in text for place in LOCAL_PLACES):
            reply_text = get_news(text)
        else:
            reply_text = get_ai_response(text)

        if reply_text:
            try:
                api.update_status(
                    status=f"@{mention.user.screen_name} {reply_text}",
                    in_reply_to_status_id=mention.id
                )
                print(f"✅ Replied to @{mention.user.screen_name}")
            except Exception as e:
                print(f"❌ Failed to reply: {e}")

# --- Bot Loop ---
def run_bot():
    while True:
        process_mentions()
        time.sleep(60)  # Check every 60 seconds

# --- FastAPI App ---
app = FastAPI()

@app.get("/")
def root():
    return {"message": "X Bot is running."}

# --- Run Bot in Background ---
threading.Thread(target=run_bot, daemon=True).start()
