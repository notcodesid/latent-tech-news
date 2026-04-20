import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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

def filter_stories(stories: list[dict], preference: str = "ai") -> list[dict]:
    keywords = ["AI", "LLM", "OpenAI", "Anthropic", "model", "agent", "GPT", "Claude", "Mistral", "Llama"]
    filtered = []
    for s in stories:
        title_upper = s["title"].upper()
        if any(k.upper() in title_upper for k in keywords):
            filtered.append(s)
    return filtered

if __name__ == "__main__":
    stories = fetch_hn_front_page()
    print(f"Fetched {len(stories)} stories from HN front page")
    
    filtered = filter_stories(stories)
    print(f"\nFiltered {len(filtered)} AI-related stories:")
    for s in filtered[:5]:
        print(f"  • {s['title']} ({s['points']} pts)")
        print(f"    {s['url']}\n")