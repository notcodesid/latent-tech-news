import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

SENT_LOG_FILE = "sent_log.json"

# ─── Load/Save Sent URLs ──────────────────────────────────
def load_sent_urls() -> set:
    if not os.path.exists(SENT_LOG_FILE):
        return set()
    with open(SENT_LOG_FILE, "r") as f:
        data = json.load(f)
    return set(data.get("urls", []))

def save_sent_urls(urls: set):
    with open(SENT_LOG_FILE, "w") as f:
        json.dump({"urls": list(urls)}, f)

# ─── 1. Fetch HN ──────────────────────────────────────────
def fetch_hn_front_page() -> list[dict]:
    url = "https://hn.algolia.com/api/v1/search?tags=front_page"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    return [
        {
            "title": h["title"],
            "url": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
            "points": h["points"],
            "comments": h.get("num_comments", 0),
        }
        for h in hits
    ]

# ─── 2. Filter AI stories ─────────────────────────────────
def filter_stories(stories: list[dict], sent_urls: set) -> list[dict]:
    keywords = ["AI", "LLM", "OpenAI", "Anthropic", "model", "agent", "GPT", "Claude", "Mistral", "Llama"]
    filtered = []
    for s in stories:
        if any(k.upper() in s["title"].upper() for k in keywords):
            if s["url"] not in sent_urls:  # skip already sent
                filtered.append(s)
    return sorted(filtered, key=lambda x: x["points"], reverse=True)[:3]

# ─── 3. Summarize via Groq ───────────────────────────────
def summarize_story(story: dict) -> str:
    prompt = f"""you're texting a founder friend. super casual. lowercase only. max 2 short sentences.

story: "{story['title']}"
link: {story['url']}

example: yo atlassian is collecting user data to train ai now lmao. {story['url']}

write yours:"""

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 80,
            "temperature": 0.9,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip().lower()

# ─── 4. Send Telegram ─────────────────────────────────────
def send_telegram_message(text: str) -> dict:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()

# ─── 5. Main ──────────────────────────────────────────────
def main():
    sent_urls = load_sent_urls()
    
    stories = fetch_hn_front_page()
    filtered = filter_stories(stories, sent_urls)
    
    if not filtered:
        print("no new stories to send.")
        return
    
    new_urls = set()
    for s in filtered:
        msg = summarize_story(s)
        send_telegram_message(msg)
        new_urls.add(s["url"])
        print(f"sent: {s['title'][:40]}...")
    
    # Save updated log
    sent_urls.update(new_urls)
    save_sent_urls(sent_urls)
    print(f"done. {len(new_urls)} new stories sent.")

if __name__ == "__main__":
    main()