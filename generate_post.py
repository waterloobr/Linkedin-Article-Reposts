"""
generate_post.py  (news-first)
Runs every Friday. Searches for the week's MAJOR business/finance/tech news, then
picks the WBR evergreen article whose argument best explains one of those stories,
and writes a LinkedIn post tying them together. Output -> draft.json for review.

Why news-first: it guarantees the hook is a story people actually care about, and
that the article was chosen to genuinely fit the news (not a forced keyword match).
The original-article link is taken from articles.json by index, so it's always real.
"""

import os
import json
import datetime
from urllib.parse import urlparse

import anthropic

MODEL = "claude-sonnet-4-6"      # bump to "claude-opus-4-8" for stronger copy
ARTICLES_FILE = "articles.json"
DRAFT_FILE = "draft.json"

REPUTABLE_OUTLETS = (
    "Bloomberg, Reuters, The Wall Street Journal, Financial Times, "
    "The New York Times, CNBC, The Economist, Harvard Business Review, "
    "Forbes, The Atlantic, Associated Press, NBC News, BBC, Axios, Fortune, "
    "Barron's, and The Globe and Mail"
)


def looks_like_article(url):
    """Reject homepages and shallow section pages; require a real story path."""
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.netloc:
        return False
    path = p.path.strip("/")
    return len(path) >= 12 or path.count("/") >= 2


def extract_json(text):
    text = text.replace("```json", "").replace("```", "").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in model output:\n{text}")
    return json.loads(text[start:end + 1])


def no_emdash(text):
    """Backstop: strip em-dash style punctuation even if the model slips."""
    text = text.replace("—", ", ").replace(" – ", ", ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text.replace(" ,", ",").replace(",,", ",")


def build_catalog(articles):
    return "\n".join(
        f"[{i}] {a['title']} — {a['summary']}" for i, a in enumerate(articles)
    )


def generate(client, articles):
    """Return (article, result) or None if no strong major-news match this week."""
    catalog = build_catalog(articles)

    system = (
        "You write the Waterloo Business Review's weekly LinkedIn post. WBR is a "
        "student-run business publication at the University of Waterloo. Match WBR's "
        "editorial voice: analytical, specific, and confident, the way a sharp business "
        "writer actually talks, not a press release and not a LinkedIn influencer. "
        "Lead with concrete detail (names, numbers, what actually happened) over abstract "
        "framing.\n\n"
        "Write so it does NOT read as AI-generated:\n"
        "- Never use em dashes. Use commas or periods, or rewrite the sentence.\n"
        "- Avoid the two-beat antithesis ('It's not X, it's Y'; 'That's not luck, that's "
        "...'), dramatic one-line fragments, and forced rule-of-three lists.\n"
        "- Avoid filler tells: 'the whole argument', 'make no mistake', 'hard to dismiss', "
        "'worth a read', 'isn't niche anymore', 'here's the thing', 'in an era where', "
        "'speaks volumes', 'underscores'.\n"
        "- Vary sentence length naturally. Trust the reader; don't over-explain the link.\n"
        "- No emoji in the body. One or two tasteful hashtags at most.\n"
        "Be rigorous about facts and never invent news."
    )

    user = f"""STEP 1 — Find the week's biggest business news (use web search):
Search for the most SIGNIFICANT business, finance, economic, markets, technology, or
corporate news from roughly the last 2-3 weeks. Focus on MAJOR events — stories covered
widely across multiple top-tier outlets, involving major companies, governments, or
economies, that a well-read businessperson would immediately recognize as important.
Ignore minor or niche items even if they're from good outlets.

Source rules:
- Use only reputable major outlets: {REPUTABLE_OUTLETS}, or a comparably established one.
  No niche/trade blogs, aggregators, SEO sites, or press-release wires.
- The URL must be a DIRECT link to the specific article — never a homepage, section page,
  or bare domain.
- Ground every claim in what the article actually reports. Never invent events, names,
  figures, or quotes.

STEP 2 — Match to a WBR evergreen article:
{catalog}

Pick the ONE article whose central argument has a genuine, substantive connection to one
of the major stories you found — the pairing should make a reader think "that older piece
explains what's happening right now." Reject superficial keyword overlaps.

If no article connects strongly to a genuinely major story, do not force it — return
exactly {{"no_match": true}}.

STEP 3 — Write the post (roughly 90-130 words, kept tight). Three beats, in order:
1) The news: what happened, concretely and specifically.
2) The broader significance: why it matters and the larger pattern or impact.
3) The WBR connection: how the chosen article's argument frames or explains it.
Close simply by pointing readers to the original article. Cut anything that doesn't serve
those three beats. No URLs in the body. Do not write "link in comments".

FINAL output: ONLY one JSON object, no markdown fences, no other text — either
{{"no_match": true}} or:
{{"article_index": <int>, "chosen_news_headline": "...", "chosen_news_url": "...", "chosen_news_outlet": "...", "post_text": "..."}}"""

    msg = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
    )

    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    result = extract_json(text)

    if result.get("no_match"):
        return None

    idx = result.get("article_index")
    if not isinstance(idx, int) or not (0 <= idx < len(articles)):
        print(f"  invalid article_index: {idx!r}")
        return None
    if not looks_like_article(result.get("chosen_news_url", "")):
        print(f"  rejected non-article URL: {result.get('chosen_news_url')!r}")
        return None

    result["post_text"] = no_emdash(result["post_text"])
    return articles[idx], result


def main():
    with open(ARTICLES_FILE) as f:
        articles = json.load(f)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    chosen = generate(client, articles)
    if not chosen:
        print("No strong major-news match this week — skipping.")
        return

    article, result = chosen
    print(f"Article: {article['title']}")
    print(f"News:    {result['chosen_news_headline']} "
          f"({result.get('chosen_news_outlet', '?')})")

    draft = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "article_title": article["title"],
        "article_url": article["url"],          # canonical, from articles.json
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