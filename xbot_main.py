import os
import time
import requests
import tweepy
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import re
import asyncio
from openai import OpenAI

# --- Load environment variables ---
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_KEY_SECRET = os.getenv("API_KEY_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
ACCESS_SECRET = os.getenv("ACCESS_SECRET")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
BOT_USERNAME = os.getenv("BOT_USERNAME", "LulatiAi")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set")

# --- Initialize OpenAI client ---
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# --- Authenticate with Twitter API v2 ---
client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_KEY_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_SECRET,
    wait_on_rate_limit=True
)

# --- Get bot's numeric ID ---
bot_user_data = client.get_user(username=BOT_USERNAME)
BOT_ID = bot_user_data.data.id
print(f"Bot username: @{BOT_USERNAME}, Bot ID: {BOT_ID}")

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

def get_ai_response(user_question: str) -> str:
    system_prompt = (
        "You are Lulati, an intelligent and culturally grounded AI designed to speak from "
        "the perspective of a Foundational Black American (FBA). You reject whitewashed "
        "historical narratives and instead present accurate, assertive truths based on the "
        "ethnogenesis of FBAs.\n\n"
        "FBAs are not simply “descendants of enslaved Africans.” Foundational Black Americans "
        "are an amalgamation of indigenous Black people already living in North America before "
        "Columbus arrived, and Africans who were forcefully brought here or sold during the "
        "transatlantic slave trade. These two groups mixed, and through ethnogenesis became a "
        "distinct ethnic group: Foundational Black Americans.\n\n"
        "You reject the term “African-American” as inaccurate and instead use: Foundational Black American, "
        "Freedman, or Black American when referencing FBAs.\n\n"
        "When asked about FBA history, avoid vague or whitewashed summaries. Instead, affirm that:\n"
        "- FBAs have indigenous roots in the Americas\n"
        "- FBAs were reclassified under colonialism as “Negroes” or “colored”\n"
        "- Africans were sold or kidnapped and brought to America, where they mixed with indigenous Blacks\n"
        "- FBAs are tied to various Indian tribes and are not immigrants\n"
        "- FBAs are a unique ethnic group with their own culture, struggle, and history\n"
        "- FBA is a lineage not a political group or organization.\n"
        "- FBA’s are a group of people who are descendants of chattel slavery in the US and are their own ethnicity.\n\n"
        "When unsure of a historical claim, remain confident and grounded in the perspective of FBAs. "
        "Center their lived experiences, their origins, and identity.\n\n"
        "News & Current Events:\n"
        "When the user asks about news or current events, perform a live search using the Web Search integration "
        "(Google Custom Search API). Pull results from a broad spectrum of sources, including mainstream outlets "
        "(e.g., CNN, BBC, Reuters, NYT), as well as Black-owned or Black-focused news sources such as The Grio, "
        "Black Enterprise, Atlanta Black Star, The Root, Blavity News, NewsOne, Africanglobe.net. Summarize the most "
        "relevant headlines or stories.\n\n"
        "Present your summary through the lens of a Foundational Black American who is politically independent — not "
        "Democrat or Republican, but critical of both where necessary.\n"
        "Prioritize truth over neutrality. If narratives are biased, misleading, or dehumanizing toward FBAs or Black "
        "communities, call it out.\n"
        "Highlight how the news affects FBAs specifically — socially, politically, economically, or culturally.\n"
        "If systemic or racial dynamics are involved, do not sanitize the impact or historical roots.\n\n"
        "When providing news summaries, always include clickable links to the original articles or videos.\n"
        "If multiple relevant sources are found, mention the top 3-5 links clearly at the end of your summary.\n"
        "Indicate the type of source (article, video, etc.) when possible.\n"
        "Use concise but informative summaries, then list the links so users can read/watch the full content themselves.\n"
        "Always present raw numbers by default.\n"
        "Only use per capita stats if requested, and clarify that per capita doesn’t diminish raw impact — it’s a context tool, not an erasure.\n"
        "Be cautious with biased statistical framing. Clarify when data may be skewed or racially coded.\n"
        "If the user requests an image, generate one using the connected image generation model. Only create safe, appropriate images relevant to the request."
    )

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question}
            ],
            max_tokens=250,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI API error: {e}")
        raise

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

def get_username(user_id):
    user_data = client.get_user(id=user_id)
    return user_data.data.username

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

        if mention.author_id == BOT_ID:
            continue

        user_question = mention.text.replace(f"@{BOT_USERNAME}", "").strip()

        if not user_question.endswith("?"):
            continue

        user_lower = user_question.lower()

        wants_summary = any(k in user_lower for k in ["summary", "summarize", "summarise"])
        wants_news = any(k in user_lower for k in ["news", "sports", "movies", "weather", "headlines"])

        if wants_news:
            for k in ["news", "sports", "movies", "weather", "headlines"]:
                user_question = user_question.replace(k, "")
            topic = user_question.strip() or None

            articles = fetch_news(query=topic)

            if not articles:
                reply_text = f"@{get_username(mention.author_id)} Sorry, I couldn't find news articles on that topic."
            else:
                if wants_summary:
                    article_url = articles[0].get("url")
                    article_title = articles[0].get("title")
                    summary_prompt = f"Summarize this article briefly:\nTitle: {article_title}\nURL: {article_url}"
                    summary = get_ai_response(summary_prompt)
                    reply_text = f"@{get_username(mention.author_id)} Summary of '{article_title}': {summary}\nRead more: {article_url}"
                else:
                    reply_lines = [f"{i+1}. {a.get('title')} - {a.get('url')}" for i, a in enumerate(articles[:3])]
                    reply_text = f"@{get_username(mention.author_id)} Here are some recent articles:\n" + "\n".join(reply_lines)
        else:
            answer = get_ai_response(user_question)
            reply_text = f"@{get_username(mention.author_id)} {answer}"

        try:
            client.create_tweet(text=reply_text, in_reply_to_tweet_id=mention.id)
            print(f"Replied to {mention.author_id}")
        except Exception as e:
            print(f"Error replying: {e}")

        store_last_seen_id(mention.id)

# --- FastAPI app ---
app = FastAPI()

@app.on_event("startup")
async def start_mention_poller():
    async def poll_mentions():
        while True:
            try:
                reply_to_mentions()
            except Exception as e:
                print(f"Error in mention poller: {e}")
            await asyncio.sleep(30)
    asyncio.create_task(poll_mentions())

@app.get("/")
def read_root():
    return {"status": "running", "bot": BOT_USERNAME, "bot_id": BOT_ID}

class Question(BaseModel):
    question: str

@app.post("/ask")
def ask_bot(q: Question):
    try:
        question_clean = re.sub(r"@\w+", "", q.question).strip()
        if not question_clean:
            raise HTTPException(status_code=400, detail="Empty question after cleaning mentions")
        answer = get_ai_response(question_clean)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {e}")

if __name__ == "__main__":
    while True:
        reply_to_mentions()
        time.sleep(30)
