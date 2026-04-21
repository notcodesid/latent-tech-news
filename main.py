import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

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
        }
        for h in hits
    ]

# ─── 2. Filter AI stories ─────────────────────────────────
def filter_stories(stories: list[dict]) -> list[dict]:
    keywords = ["AI", "LLM", "OpenAI", "Anthropic", "model", "agent", "GPT", "Claude", "Mistral", "Llama"]
    filtered = []
    for s in stories:
        if any(k.upper() in s["title"].upper() for k in keywords):
            filtered.append(s)
    return sorted(filtered, key=lambda x: x["points"], reverse=True)[:3]  

# ─── 3. Summarize via Groq (short + lowercase) ────────────
def summarize_story(story: dict) -> str:
    prompt = f"""you're texting a founder friend. super casual. lowercase only. no punctuation except maybe a period. max 2 short sentences.

story: "{story['title']}"
link: {story['url']}

examples:
- yo atlassian is collecting user data to train ai now lmao. {story['url']}
- damn 44% of deezer uploads are ai generated. {story['url']}

now write yours:"""

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
        "disable_web_page_preview": True,  # cleaner, no previews
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()

# ─── 5. Send each story as separate message ───────────────
def main():
    print("fetching hn...")
    stories = fetch_hn_front_page()
    
    print("filtering ai stories...")
    filtered = filter_stories(stories)
    
    if not filtered:
        send_telegram_message("yo nothing interesting on hn rn lol")
        print("nothing to send.")
        return
    
    print(f"sending {len(filtered)} stories...")
    for s in filtered:
        msg = summarize_story(s)
        send_telegram_message(msg)
        print(f"sent: {msg[:40]}...")
    
    print("done.")

if __name__ == "__main__":
    main()