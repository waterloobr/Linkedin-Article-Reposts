"""
generate_post.py
Runs every Friday. Picks the week's evergreen article, uses the Anthropic API's
built-in web search to find a CURRENT, real news story from a reputable outlet,
and has Claude write a LinkedIn post tying them together. Output -> draft.json.

Quality rules baked in:
- the news must be a specific article from a major outlet (no homepages, no
  niche blogs / aggregators);
- claims must be grounded in the real article (no fabricated events);
- if no genuinely relevant recent story exists for an article, it skips to the
  next one rather than forcing a weak tie-in.
"""

import os
import json
import datetime
from urllib.parse import urlparse

import anthropic

MODEL = "claude-sonnet-4-6"      # bump to "claude-opus-4-8" for stronger copy
ARTICLES_FILE = "articles.json"
DRAFT_FILE = "draft.json"
MAX_ATTEMPTS = 5                 # how many articles to try before giving up for the week

REPUTABLE_OUTLETS = (
    "Bloomberg, Reuters, The Wall Street Journal, Financial Times, "
    "The New York Times, CNBC, The Economist, Harvard Business Review, "
    "Forbes, The Atlantic, Associated Press, NBC News, BBC, Axios, Fortune, "
    "Barron's, and The Globe and Mail"
)


def candidate_order(articles):
    """Start at the week's article, then walk the rest of the list in order."""
    week = datetime.date.today().isocalendar().week
    n = len(articles)
    return [articles[(week + i) % n] for i in range(n)]


def looks_like_article(url):
    """Reject homepages and shallow section pages; require a real story path."""
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.netloc:
        return False
    path = p.path.strip("/")
    # a real article URL has a substantial path; "cnbc.com/" or "/markets" won't pass
    return len(path) >= 12 or path.count("/") >= 2


def extract_json(text):
    text = text.replace("```json", "").replace("```", "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in model output:\n{text}")
    return json.loads(text[start:end + 1])


def write_post(client, article):
    """Return a result dict, or None if there's no good current match."""
    system = (
        "You write LinkedIn posts for the Waterloo Business Review, a "
        "student-run business publication at the University of Waterloo. "
        "Voice: sharp, analytical, accessible. No hashspam, no emoji walls, "
        "no 'thrilled to share'. One or two tasteful hashtags max. "
        "You are rigorous about facts and never invent news."
    )

    themes = ", ".join(article["themes"])
    user = f"""We want to resurface an evergreen WBR article by tying it to a CURRENT news story.

EVERGREEN ARTICLE
Title: {article['title']}
Summary: {article['summary']}
URL: {article['url']}

STEP 1 — Find the news (use web search):
- Find a real news story published within the last ~14 days that genuinely connects
  to the article's argument (topics: {themes}).
- It MUST come from a major, reputable outlet such as: {REPUTABLE_OUTLETS}, or a
  comparably established business/news publication. Do NOT use niche or trade-specific
  blogs, content aggregators, SEO sites, or press-release wires.
- The URL must be the DIRECT link to the specific article — never a homepage, a
  section/category page, or a bare domain.
- Ground every factual claim strictly in what that article actually reports. Never
  invent events, company names, statistics, or quotes. If you're not certain a detail
  is real, leave it out.
- IMPORTANT: if you cannot find a genuinely relevant, recent story from a credible
  outlet, do not force it. Instead return exactly: {{"no_match": true}}

STEP 2 — If you found a good match, write a LinkedIn post (~100-160 words) that:
- opens with a hook tied to the current news story
- bridges to the evergreen article's central argument
- ends with a soft prompt to read the original (do NOT write "link in comments";
  the links are appended automatically below the post)
- do NOT put any URLs in the body text

Your FINAL message must be ONLY one valid JSON object, no markdown fences, no other
text — either {{"no_match": true}} or:
{{"chosen_news_headline": "...", "chosen_news_url": "...", "chosen_news_outlet": "...", "post_text": "..."}}"""

    msg = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
    )

    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    result = extract_json(text)

    if result.get("no_match"):
        return None
    if not looks_like_article(result.get("chosen_news_url", "")):
        # model returned a homepage / junk URL despite instructions — treat as no match
        print(f"  rejected non-article URL: {result.get('chosen_news_url')!r}")
        return None
    return result


def main():
    with open(ARTICLES_FILE) as f:
        articles = json.load(f)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    chosen = None
    for article in candidate_order(articles)[:MAX_ATTEMPTS]:
        print(f"Trying: {article['title']}")
        result = write_post(client, article)
        if result:
            chosen = (article, result)
            break
        print("  no strong match, moving on")

    if not chosen:
        print(f"No solid news match across {MAX_ATTEMPTS} articles this week — skipping.")
        return

    article, result = chosen
    print(f"\nMatched: {result['chosen_news_headline']} "
          f"({result.get('chosen_news_outlet', '?')})")

    draft = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "article_title": article["title"],
        "article_url": article["url"],
        "news_headline": result["chosen_news_headline"],
        "news_outlet": result.get("chosen_news_outlet", ""),
        "news_url": result["chosen_news_url"],
        "post_text": result["post_text"],
        "final_body": (
            f"{result['post_text']}\n\n"
            f"📄 Original article: {article['url']}\n"
            f"📰 In the news: {result['chosen_news_url']}"
        ),
    }

    with open(DRAFT_FILE, "w") as f:
        json.dump(draft, f, indent=2)

    print("\n--- DRAFT ---\n")
    print(draft["final_body"])


if __name__ == "__main__":
    main()