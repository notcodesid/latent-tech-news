import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

SENT_LOG_FILE = "sent_log.json"
SUBSCRIBERS_FILE = "subscribers.json"

# ─── Load/Save Helpers ────────────────────────────────────
def load_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)

def save_json(path: str, data):
    with open(path, "w") as f:
        json.dump(data, f)

# ─── Collect New Subscribers ──────────────────────────────
def collect_subscribers() -> list[str]:
    """Get chat IDs from people who messaged the bot recently."""
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset=-50"
    resp = requests.get(url, timeout=30)
    if not resp.ok:
        return []
    
    updates = resp.json().get("result", [])
    subscribers = set(load_json(SUBSCRIBERS_FILE, []))
    
    for u in updates:
        msg = u.get("message", {})
        chat = msg.get("chat", {})
        
        # Only collect private chats (not group chats)
        if chat.get("type") == "private":
            chat_id = str(chat["id"])
            subscribers.add(chat_id)
            
            # Optional: send welcome on first join
            text = msg.get("text", "").lower().strip()
            if text in ["/start", "start", "hi", "hello"]:
                send_to_chat(chat_id, "yo, you're in. i'll send ai/tech news every 3 hours. lowercase only lmao.")
    
    save_json(SUBSCRIBERS_FILE, list(subscribers))
    return list(subscribers)

# ─── Send to One Chat ─────────────────────────────────────
def send_to_chat(chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    requests.post(url, json=payload, timeout=30)

# ─── Fetch HN ─────────────────────────────────────────────
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

# ─── Filter AI Stories ────────────────────────────────────
def filter_stories(stories: list[dict], sent_urls: set) -> list[dict]:
    keywords = ["AI", "LLM", "OpenAI", "Anthropic", "model", "agent", "GPT", "Claude", "Mistral", "Llama"]
    filtered = []
    for s in stories:
        if any(k.upper() in s["title"].upper() for k in keywords):
            if s["url"] not in sent_urls:
                filtered.append(s)
    return sorted(filtered, key=lambda x: x["points"], reverse=True)[:3]

# ─── Summarize via Groq ───────────────────────────────────
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

# ─── Main ─────────────────────────────────────────────────
def main():
    # Step 1: Collect anyone who messaged the bot
    subscribers = collect_subscribers()
    if not subscribers:
        print("no subscribers yet.")
        return
    
    print(f"{len(subscribers)} subscribers found")
    
    # Step 2: Fetch and filter news
    sent_urls = set(load_json(SENT_LOG_FILE, {}).get("urls", []))
    stories = fetch_hn_front_page()
    filtered = filter_stories(stories, sent_urls)
    
    if not filtered:
        print("no new stories.")
        return
    
    # Step 3: Send to ALL subscribers
    new_urls = set()
    for s in filtered:
        msg = summarize_story(s)
        for chat_id in subscribers:
            send_to_chat(chat_id, msg)
        new_urls.add(s["url"])
        print(f"sent to {len(subscribers)} people: {s['title'][:40]}...")
    
    # Step 4: Save what we sent
    sent_urls.update(new_urls)
    save_json(SENT_LOG_FILE, {"urls": list(sent_urls)})

if __name__ == "__main__":
    main()