import os
import time
import tweepy
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- API Keys ---
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL")

# --- Authenticate with X (Twitter) API ---
auth = tweepy.OAuth1UserHandler(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
api = tweepy.API(auth)

BOT_ID = api.verify_credentials().id
BOT_HANDLE = api.me().screen_name.lower()
last_seen_id = None

# --- Local city/state list for detection ---
LOCAL_PLACES = [
    "chicago", "new york", "los angeles", "atlanta", "houston", "dallas",
    "miami", "washington", "north carolina", "south carolina", "detroit",
    "baltimore", "philadelphia", "new orleans", "oakland"
]

# --- Utility Functions ---
def get_news(query):
    """Fetch top 3 news articles matching the query."""
    url = (
        f"https://newsapi.org/v2/everything?q={query}"
        f"&language=en&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
    )
    try:
        r = requests.get(url)
        data = r.json()
        if "articles" in data and data["articles"]:
            headlines = [
                f"{a.get('title', 'No title')} - {a.get('url', '')}"
                for a in data["articles"]
            ]
            return "\n".join(headlines)
        return "No recent news found on that topic."
    except Exception as e:
        return f"Error fetching news: {e}"

def get_ai_response(message):
    """Call AI backend for a reply in FBA voice."""
    try:
        payload = {"message": message}
        r = requests.post(AI_BACKEND_URL, json=payload)
        if r.status_code == 200:
            return r.json().get("reply", "I got nothing to say on that.")
        return "My AI brain is feeling a little slow right now."
    except Exception as e:
        return f"Error contacting AI backend: {e}"

def find_local_place(text):
    """Check if text contains a city/state from the list."""
    lowered = text.lower()
    return next((place for place in LOCAL_PLACES if place in lowered), None)

def clean_m_
