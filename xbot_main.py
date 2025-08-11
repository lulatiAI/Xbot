import os
import time
import requests
import tweepy
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

# --- Load environment variables ---
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL")
BOT_USERNAME = os.getenv("BOT_USERNAME", "LulatiAi")  # Default bot username

# --- Authenticate with X API v2 ---
client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_KEY_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
    wait_on_rate_limit=True
)

# --- Get bot's numeric ID from username ---
bot_user_data = client.get_user(username=BOT_USERNAME)
BOT_ID = bot_user_data.data.id
print(f"Bot username: @{BOT_USERNAME}, Bot ID: {BOT_ID}")

# --- Track last processed mention ---
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

# --- Fetch news articles from NewsAPI ---
def fetch_news(query=None, category=None, country="us"):
    url = "https://newsapi.org/v2/top-headlines"
    params = {"apiKey": NEWS_API_KEY, "country": country}
    if query:
        params["q"] = query
    if category:
        params["category"] = category
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"NewsAPI error: {response.status_code} {response.text}")
        return []
    data = response.json()
    return data.get("articles", [])

# --- Helper to get username from ID ---
def get_username(user_id):
    user_data = client.get_user(id=user_id)
    return user_data.data.username

# --- Process mentions ---
def reply_to_mentions():
    print("Checking for mentions...")
    last_seen_id = retrieve_last_seen_id()

    mentions = client.get_users_mentions(
        id=BOT_ID,
        since_id=last_seen_id,
        tweet_fields=["created_at", "author_id", "text"]
    )

    if not mentions.data:
        print("No new mentions.")
        return

    for mention in reversed(mentions.data):
        print(f"Processing mention from user_id={mention.author_id}: {mention.text}")

        # Skip if self-reply
        if mention.author_id == BOT_ID:
            continue

        # Remove @botname from text
        user_question = mention.text.replace(f"@{BOT_USERNAME}", "").strip()

        # Only reply if it's a question
        if not user_question.endswith("?"):
            continue

        user_lower = user_question.lower()

        # Detect if user is asking for news or summaries
        wants_summary = "summary" in user_lower or "summarize" in user_lower or "summarise" in user_lower
        # Check if user asks about news or related topics
        wants_news = any(keyword in user_lower for keyword in ["news", "sports", "movies", "weather", "headlines"])

        if wants_news:
            # Extract possible topic or location from question, naive approach: remove keywords
            for keyword in ["news", "sports", "movies", "weather", "headlines"]:
                user_question = user_question.replace(keyword, "")
            topic = user_question.strip() or None

            # Fetch news (country default "us")
            articles = fetch_news(query=topic)

            if not articles:
                reply_text = f"@{get_username(mention.author_id)} Sorry, I couldn't find news articles on that topic."
            else:
                # If summary requested, ask AI backend to summarize first article
                if wants_summary:
                    article_url = articles[0].get("url")
                    article_title = articles[0].get("title")
                    summary_prompt = f"Summarize this article briefly:\nTitle: {article_title}\nURL: {article_url}"
                    summary = get_ai_response(summary_prompt)
                    reply_text = f"@{get_username(mention.author_id)} Summary of '{article_title}': {summary}\nRead more: {article_url}"
                else:
                    # Just list top 3 article titles + URLs
                    reply_lines = [f"{i+1}. {a.get('title')} - {a.get('url')}" for i, a in enumerate(articles[:3])]
                    reply_text = f"@{get_username(mention.author_id)} Here are some recent articles:\n" + "\n".join(reply_lines)
        else:
            # Default: just pass to AI backend for general question answering
            answer = get_ai_response(user_question)
            reply_text = f"@{get_username(mention.author_id)} {answer}"

        try:
            client.create_tweet(
                text=reply_text,
                in_reply_to_tweet_id=mention.id
            )
            print(f"Replied to {mention.author_id}")
        except Exception as e:
            print(f"Error replying: {e}")

        store_last_seen_id(mention.id)

# --- FastAPI app for health check and question testing ---
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "running", "bot": BOT_USERNAME, "bot_id": BOT_ID}

# New: POST /ask endpoint to test your bot with custom questions
class Question(BaseModel):
    question: str

@app.post("/ask")
def ask_bot(q: Question):
    answer = get_ai_response(q.question)
    return {"answer": answer}

# --- Background polling loop ---
if __name__ == "__main__":
    while True:
        reply_to_mentions()
        time.sleep(30)  # Check every 30 seconds