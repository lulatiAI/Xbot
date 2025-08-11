import os
import logging
import tweepy
import requests
from fastapi import FastAPI
from dotenv import load_dotenv

# Load environment variables from .env if running locally
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL")

# Validate required env vars
required_vars = {
    "API_KEY": API_KEY,
    "API_KEY_SECRET": API_KEY_SECRET,
    "ACCESS_TOKEN": ACCESS_TOKEN,
    "ACCESS_SECRET": ACCESS_SECRET,
    "BEARER_TOKEN": BEARER_TOKEN,
    "NEWS_API_KEY": NEWS_API_KEY
}

for var, value in required_vars.items():
    if not value:
        logger.error(f"Missing environment variable: {var}")

# Twitter authentication
auth = tweepy.OAuth1UserHandler(API_KEY, API_KEY_SECRET, ACCESS_TOKEN, ACCESS_SECRET)
twitter_api = tweepy.API(auth)

# FastAPI app
app = FastAPI()

def get_top_headlines():
    """Fetch top news headlines from NewsAPI"""
    url = f"https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    if response.status_code != 200:
        logger.error(f"News API error: {response.status_code} - {response.text}")
        return []
    data = response.json()
    return [article["title"] for article in data.get("articles", []) if "title" in article]

def tweet_news_headlines():
    """Post top news headlines to Twitter"""
    headlines = get_top_headlines()
    if not headlines:
        logger.warning("No headlines to tweet.")
        return
    for headline in headlines[:5]:  # limit to 5 tweets at a time
        try:
            twitter_api.update_status(headline)
            logger.info(f"Tweeted: {headline}")
        except Exception as e:
            logger.error(f"Error tweeting headline: {e}")

@app.get("/")
def home():
    return {"message": "XBot is running"}

@app.post("/tweet-news")
def tweet_news():
    tweet_news_headlines()
    return {"status": "success", "message": "News headlines tweeted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
