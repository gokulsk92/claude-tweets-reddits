"""
Uses Claude Haiku to categorize posts into marketing/sales buckets
and extract a one-line actionable insight per post.
Falls back to keyword-based categorization if no API key is set.
"""

import json
import os
import re
import time
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "posts.json"

CATEGORIES = [
    "Performance Marketing & Ads",
    "Marketing Automation",
    "Field & Event Marketing",
    "ABM (Account-Based Marketing)",
    "Pipeline Acceleration",
    "Integrated Marketing",
    "Content & SEO",
    "Sales Enablement",
    "General / Other",
]

KEYWORD_MAP = {
    "Performance Marketing & Ads": [
        "ads", "advertising", "ppc", "paid", "google ads", "meta ads",
        "facebook ads", "linkedin ads", "performance", "roas", "cpm", "cpc",
        "retargeting", "programmatic",
    ],
    "Marketing Automation": [
        "automation", "workflow", "hubspot", "marketo", "pardot", "zapier",
        "sequence", "drip", "trigger", "email automation", "nurture",
    ],
    "Field & Event Marketing": [
        "event", "conference", "webinar", "field marketing", "trade show",
        "booth", "sponsorship", "in-person", "virtual event",
    ],
    "ABM (Account-Based Marketing)": [
        "abm", "account-based", "target account", "account list",
        "personalized outreach", "key account", "enterprise",
    ],
    "Pipeline Acceleration": [
        "pipeline", "deal", "close", "revenue", "forecast", "crm",
        "salesforce", "opportunity", "objection", "proposal",
    ],
    "Integrated Marketing": [
        "integrated", "omnichannel", "multi-channel", "campaign",
        "go-to-market", "gtm", "launch", "brand",
    ],
    "Content & SEO": [
        "content", "seo", "blog", "copywriting", "landing page",
        "social media", "linkedin", "twitter", "copy",
    ],
    "Sales Enablement": [
        "sales enablement", "playbook", "battlecard", "demo", "cold email",
        "outreach", "prospecting", "sdr", "bdr", "sales rep",
    ],
}


def keyword_categorize(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "General / Other"


def keyword_insight(title: str) -> str:
    return f"Claude used in context of: {title[:120]}"


def claude_categorize_batch(posts: list[dict]) -> list[dict]:
    try:
        import anthropic
    except ImportError:
        print("[warn] anthropic package not installed. Using keyword categorization.")
        for p in posts:
            p["category"] = keyword_categorize(p["title"], p["summary"])
            p["key_insight"] = keyword_insight(p["title"])
        return posts

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[warn] ANTHROPIC_API_KEY not set. Using keyword categorization.")
        for p in posts:
            p["category"] = keyword_categorize(p["title"], p["summary"])
            p["key_insight"] = keyword_insight(p["title"])
        return posts

    client = anthropic.Anthropic(api_key=api_key)

    categories_list = "\n".join(f"- {c}" for c in CATEGORIES)

    for i, post in enumerate(posts):
        text_snippet = f"Title: {post['title']}\nSummary: {post['summary'][:400]}"
        prompt = f"""You are analyzing a social media post/article about Claude AI being used in marketing or sales.

Post:
{text_snippet}

Categories (pick exactly one):
{categories_list}

Reply with JSON only, no explanation:
{{
  "category": "<one of the categories above>",
  "key_insight": "<one actionable sentence: what was Claude used for and what result/benefit was mentioned>"
}}"""

        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            # Extract JSON from response
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                parsed = json.loads(match.group())
                cat = parsed.get("category", "General / Other")
                # Validate category
                if cat not in CATEGORIES:
                    cat = keyword_categorize(post["title"], post["summary"])
                post["category"] = cat
                post["key_insight"] = parsed.get("key_insight", keyword_insight(post["title"]))
            else:
                post["category"] = keyword_categorize(post["title"], post["summary"])
                post["key_insight"] = keyword_insight(post["title"])
        except Exception as e:
            print(f"  [warn] Claude API error for post {i}: {e}")
            post["category"] = keyword_categorize(post["title"], post["summary"])
            post["key_insight"] = keyword_insight(post["title"])

        # Small delay to avoid rate limiting
        if i < len(posts) - 1:
            time.sleep(0.3)

    return posts


def categorize_uncategorized() -> int:
    if not DATA_FILE.exists():
        print("No data file found.")
        return 0

    with open(DATA_FILE) as f:
        data = json.load(f)

    posts = data.get("posts", [])
    uncategorized = [p for p in posts if not p.get("category")]

    if not uncategorized:
        print("All posts already categorized.")
        return 0

    print(f"Categorizing {len(uncategorized)} posts...")
    categorized = claude_categorize_batch(uncategorized)

    # Merge back
    cat_map = {p["id"]: p for p in categorized}
    for i, post in enumerate(posts):
        if post["id"] in cat_map:
            posts[i] = cat_map[post["id"]]

    data["posts"] = posts
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Done. Categorized {len(uncategorized)} posts.")
    return len(uncategorized)


if __name__ == "__main__":
    categorize_uncategorized()
