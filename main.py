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
            "comments": h.get("num_comments", 0),
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
    return sorted(filtered, key=lambda x: x["points"], reverse=True)[:5]

# ─── 3. Summarize via Groq (FREE) ─────────────────────────
def summarize_story(story: dict) -> str:
    prompt = f"""You are a VC associate writing a daily briefing for a busy founder.

Story: "{story['title']}"
URL: {story['url']}

Write exactly 2 lines:
1) What happened (product name, company, or event if mentioned)
2) Why it matters to a technical founder building in AI

Be concise. No fluff. No markdown headers."""

    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.1-8b-instant",  # fast, free, good enough
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 150,
            "temperature": 0.7,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

# ─── 4. Send Telegram ─────────────────────────────────────
def send_telegram_message(text: str) -> dict:
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()

# ─── 5. Build + Send Digest ───────────────────────────────
def build_digest(stories: list[dict]) -> str:
    lines = ["🧠 *Latent Tech Digest* — AI/LLM/Agents\n"]
    for i, s in enumerate(stories, 1):
        summary = summarize_story(s)
        lines.append(f"*{i}. {s['title']}*")
        lines.append(f"{summary}")
        lines.append(f"🔗 [Link]({s['url']}) · {s['points']} pts · {s['comments']} comments\n")
    return "\n".join(lines)

def main():
    print("Fetching HN front page...")
    stories = fetch_hn_front_page()
    
    print("Filtering AI stories...")
    filtered = filter_stories(stories)
    
    if not filtered:
        send_telegram_message("🫠 No AI stories on HN front page right now.")
        print("Nothing to send.")
        return
    
    print(f"Summarizing {len(filtered)} stories via Groq...")
    digest = build_digest(filtered)
    
    print("Sending to Telegram...")
    send_telegram_message(digest)
    print("Done. Digest sent.")

if __name__ == "__main__":
    main()