"""
generate_post.py
Runs every Friday. Picks the week's evergreen article, uses the Anthropic API's
built-in web search to find a current news story related to its themes, and has
Claude write a LinkedIn post tying them together. Output -> draft.json for review.

The web search runs server-side on Anthropic's infrastructure, so it doesn't
depend on the GitHub runner's IP (which Google News blocks).
"""

import os
import json
import datetime

import anthropic

MODEL = "claude-sonnet-4-6"   # bump to "claude-opus-4-8" for stronger copy
ARTICLES_FILE = "articles.json"
DRAFT_FILE = "draft.json"


def pick_article(articles):
    """Stateless rotation: ISO week number cycles through the list."""
    week = datetime.date.today().isocalendar().week
    return articles[week % len(articles)]


def extract_json(text):
    """Pull the JSON object out of the model's final text, fences or not."""
    text = text.replace("```json", "").replace("```", "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in model output:\n{text}")
    return json.loads(text[start:end + 1])


def write_post(article):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system = (
        "You write LinkedIn posts for the Waterloo Business Review, a "
        "student-run business publication at the University of Waterloo. "
        "Voice: sharp, analytical, accessible. No hashspam, no emoji walls, "
        "no 'thrilled to share'. One or two tasteful hashtags max."
    )

    themes = ", ".join(article["themes"])
    user = f"""We are resurfacing an evergreen WBR article and tying it to a CURRENT news story.

EVERGREEN ARTICLE
Title: {article['title']}
Summary: {article['summary']}
URL: {article['url']}

Step 1: Search the web for a recent (last ~2 weeks) news story related to any of
these topics: {themes}. Choose the ONE most genuinely relevant, real, current story.

Step 2: Write a LinkedIn post (roughly 100-160 words) that:
- opens with a hook tied to the current news story you chose
- bridges to the evergreen article's central argument
- ends with a soft prompt to read the original
Do NOT paste any URLs into the body text; they are added separately.

Your FINAL message must be ONLY a valid JSON object, no markdown fences and no
other text, in exactly this shape:
{{"chosen_news_headline": "...", "chosen_news_url": "...", "post_text": "..."}}"""

    msg = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 5,
        }],
    )

    text = "".join(b.text for b in msg.content if b.type == "text").strip()
    return extract_json(text)


def main():
    with open(ARTICLES_FILE) as f:
        articles = json.load(f)

    article = pick_article(articles)
    print(f"Selected article: {article['title']}")

    result = write_post(article)
    print(f"Matched news: {result['chosen_news_headline']}")

    draft = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "article_title": article["title"],
        "article_url": article["url"],
        "news_headline": result["chosen_news_headline"],
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