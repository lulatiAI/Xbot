import os
import time
import requests
import tweepy
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import re

# --- Load environment variables ---
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
AI_BACKEND_URL = os.getenv("AI_BACKEND_URL")
BOT_USERNAME = os.getenv("BOT_USERNAME", "LulatiAi")  # Default bot username (without @)

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
def get_ai_response(user_question: str) -> str:
    try:
        resp = requests.post(
            f"{AI_BACKEND_URL}/chat",
            json={"prompt": user_question},
            timeout=15
        )
        if resp.status_code == 200:
            json_resp = resp.json()
            # Support either "response" or fallback key for answer
            return json_resp.get("response") or json_resp.get("answer") or "I’m not sure how to answer that right now."
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

        # Remove @botname from text (case insensitive)
        pattern = re.compile(rf"@{re.escape(BOT_USERNAME)}", re.IGNORECASE)
        user_question = pattern.sub("", mention.text).strip()

        # Only reply if it's a question
        if not user_question.endswith("?"):
            continue

        user_lower = user_question.lower()

        # Detect if user is asking for news or summaries
        wants_summary = any(keyword in user_lower for keyword in ["summary", "summarize", "summarise"])
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

class Question(BaseModel):
    question: str

@app.post("/ask")
def ask_bot(q: Question):
    # Validate bot mention present
    if f"@{BOT_USERNAME}".lower() not in q.question.lower():
        raise HTTPException(status_code=400, detail=f"Question must mention @{BOT_USERNAME}")
    
    # Extract question after mention
    pattern = re.compile(rf"@{re.escape(BOT_USERNAME)}", re.IGNORECASE)
    parts = pattern.split(q.question, maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        raise HTTPException(status_code=400, detail="No question text after bot mention")

    clean_question = parts[1].strip()

    answer = get_ai_response(clean_question)
    return {"answer": answer}

# Optional: add /chat endpoint same as /ask
@app.post("/chat")
def chat_bot(q: Question):
    return ask_bot(q)

# --- Background polling loop (if running as script) ---
if __name__ == "__main__":
    while True:
        reply_to_mentions()
        time.sleep(30)  # Check every 30 seconds
