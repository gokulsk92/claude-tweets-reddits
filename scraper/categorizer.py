"""
Uses Claude Haiku to:
1. Verify the post actually describes Claude AI being USED in marketing/sales (not just mentioned)
2. Extract a specific, actionable insight: what task + what measurable outcome
3. Categorize into one of the defined marketing buckets
Posts that don't pass the relevance gate are marked skip=True and excluded.
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
        "social media", "copy",
    ],
    "Sales Enablement": [
        "sales enablement", "playbook", "battlecard", "demo", "cold email",
        "outreach", "prospecting", "sdr", "bdr",
    ],
}

CLAUDE_PROMPT = """You are a strict curator for a marketing intelligence feed. Your job is to decide whether a post contains a real, actionable use case of Claude AI in marketing or sales — and extract the insight if it does.

**Relevance criteria (ALL must be true to keep):**
1. The post describes Claude AI (by Anthropic) being actively USED — not just mentioned or compared
2. The use is in marketing, sales, advertising, or revenue-related work
3. There is a specific task described (e.g. "wrote cold emails", "built an ABM sequence", "automated ad copy")
4. There is a concrete outcome, result, or clear benefit (e.g. "saved 4 hours/week", "2x reply rate", "cut ad copy time by 70%")

**If any criterion is missing, set skip to true.**

Post:
Title: {title}
Content: {content}

Categories (pick one only if keeping):
{categories}

Reply with JSON only:
{{
  "skip": true/false,
  "skip_reason": "<only if skip=true: one short reason>",
  "category": "<category name or null if skipping>",
  "key_insight": "<if keeping: one crisp sentence — WHAT Claude did + WHAT the result was. No filler. No echoing the title. Must include both the specific task and the specific outcome.>"
}}"""


def keyword_categorize(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "General / Other"


def categorize_with_claude(client, post: dict) -> dict:
    categories_list = "\n".join(f"- {c}" for c in CATEGORIES)
    content_snippet = (post.get("summary") or "")[:600]
    if not content_snippet:
        content_snippet = post["title"]

    prompt = CLAUDE_PROMPT.format(
        title=post["title"],
        content=content_snippet,
        categories=categories_list,
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            if parsed.get("skip"):
                post["skip"] = True
                post["skip_reason"] = parsed.get("skip_reason", "not relevant")
                post["category"] = None
                post["key_insight"] = None
            else:
                cat = parsed.get("category")
                if cat not in CATEGORIES:
                    cat = keyword_categorize(post["title"], post.get("summary", ""))
                post["skip"] = False
                post["category"] = cat
                post["key_insight"] = parsed.get("key_insight") or None
        else:
            post["skip"] = True
            post["skip_reason"] = "unparseable API response"
    except Exception as e:
        print(f"  [warn] Claude API error: {e}")
        # On API error, keep post with keyword categorization (don't discard)
        post["skip"] = False
        post["category"] = keyword_categorize(post["title"], post.get("summary", ""))
        post["key_insight"] = None

    return post


def categorize_uncategorized() -> int:
    if not DATA_FILE.exists():
        print("No data file found.")
        return 0

    with open(DATA_FILE) as f:
        data = json.load(f)

    posts = data.get("posts", [])
    uncategorized = [p for p in posts if p.get("category") is None and not p.get("skip")]

    if not uncategorized:
        print("All posts already categorized.")
        return 0

    print(f"Categorizing {len(uncategorized)} posts with Claude Haiku...")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[warn] No ANTHROPIC_API_KEY — using keyword fallback (no filtering).")
        for p in uncategorized:
            p["skip"] = False
            p["category"] = keyword_categorize(p["title"], p.get("summary", ""))
            p["key_insight"] = None
    else:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            for i, post in enumerate(uncategorized):
                categorize_with_claude(client, post)
                if i < len(uncategorized) - 1:
                    time.sleep(0.3)
        except ImportError:
            print("[warn] anthropic package not installed. Using keyword fallback.")
            for p in uncategorized:
                p["skip"] = False
                p["category"] = keyword_categorize(p["title"], p.get("summary", ""))
                p["key_insight"] = None

    # Merge updates back
    updated_map = {p["id"]: p for p in uncategorized}
    for i, post in enumerate(posts):
        if post["id"] in updated_map:
            posts[i] = updated_map[post["id"]]

    skipped = sum(1 for p in posts if p.get("skip"))
    kept = sum(1 for p in posts if not p.get("skip") and p.get("category"))
    print(f"Done: {kept} kept, {skipped} skipped as irrelevant.")

    data["posts"] = posts
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

    return len(uncategorized)


if __name__ == "__main__":
    categorize_uncategorized()
