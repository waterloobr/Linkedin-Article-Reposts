"""
generate_post.py
Runs every Friday. Picks the week's evergreen article, finds a current news
story related to its themes, and has Claude write a LinkedIn post tying them
together. Output is written to draft.json for review before publishing.
"""

import os
import json
import datetime
import urllib.parse
import xml.etree.ElementTree as ET

import requests
import anthropic

# ---- config -------------------------------------------------------------
MODEL = "claude-sonnet-4-6"   # bump to "claude-opus-4-8" for higher-quality copy
NEWS_PER_THEME = 4            # headlines pulled per theme query
ARTICLES_FILE = "articles.json"
DRAFT_FILE = "draft.json"


def pick_article(articles):
    """Stateless rotation: ISO week number cycles through the list."""
    week = datetime.date.today().isocalendar().week
    return articles[week % len(articles)]


def fetch_news(themes):
    """Pull recent headlines from Google News RSS (free, no API key)."""
    items = []
    for theme in themes:
        q = urllib.parse.quote(theme)
        url = (
            f"https://news.google.com/rss/search?q={q}+when:14d"
            f"&hl=en-CA&gl=CA&ceid=CA:en"
        )
        try:
            resp = requests.get(url, timeout=20,
                                headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for item in root.findall(".//item")[:NEWS_PER_THEME]:
                items.append({
                    "headline": item.findtext("title", "").strip(),
                    "link": item.findtext("link", "").strip(),
                    "source": (item.findtext("source") or "").strip(),
                    "pub_date": item.findtext("pubDate", "").strip(),
                })
        except Exception as e:
            print(f"  ! news fetch failed for '{theme}': {e}")
    return items


def write_post(article, news_items):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system = (
        "You write LinkedIn posts for the Waterloo Business Review, a "
        "student-run business publication at the University of Waterloo. "
        "Voice: sharp, analytical, accessible. No hashspam, no emoji walls, "
        "no 'thrilled to share'. One or two tasteful hashtags max."
    )

    user = f"""We are resurfacing an evergreen WBR article and tying it to a current news story.

EVERGREEN ARTICLE
Title: {article['title']}
Summary: {article['summary']}
URL: {article['url']}

CANDIDATE CURRENT NEWS (choose the ONE most genuinely relevant; do not invent facts beyond these headlines):
{json.dumps(news_items, indent=2)}

Write a LinkedIn post (roughly 100-160 words) that:
- opens with a hook tied to the current news story you chose
- bridges to the evergreen article's argument
- ends with a soft prompt to read the original
Do NOT paste the URLs into the body text; they are added separately.

Return ONLY valid JSON, no markdown fences, in this exact shape:
{{"chosen_news_headline": "...", "chosen_news_url": "...", "post_text": "..."}}"""

    msg = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    raw = "".join(b.text for b in msg.content if b.type == "text").strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def main():
    with open(ARTICLES_FILE) as f:
        articles = json.load(f)

    article = pick_article(articles)
    print(f"Selected article: {article['title']}")

    news = fetch_news(article["themes"])
    print(f"Pulled {len(news)} candidate headlines")
    if not news:
        raise SystemExit("No news found — aborting this week.")

    result = write_post(article, news)

    draft = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "article_title": article["title"],
        "article_url": article["url"],
        "news_headline": result["chosen_news_headline"],
        "news_url": result["chosen_news_url"],
        "post_text": result["post_text"],
        # final body LinkedIn will publish, with both links appended
        "final_body": (
            f"{result['post_text']}\n\n"
            f"🔗 Original article: {article['url']}\n"
            f"📰 In the news: {result['chosen_news_url']}"
        ),
    }

    with open(DRAFT_FILE, "w") as f:
        json.dump(draft, f, indent=2)

    print("\n--- DRAFT ---\n")
    print(draft["final_body"])


if __name__ == "__main__":
    main()
