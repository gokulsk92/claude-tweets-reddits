"""
Uses Claude Haiku to:
1. Verify the post actually describes Claude AI being USED in marketing/sales
2. Extract a specific, actionable insight: what task + what outcome
3. Assign one of 5 simplified marketing categories
4. Select the daily Top Stories (most actionable, most novel)

Posts that don't pass the relevance gate are marked skip=True and excluded.
"""

import json
import os
import re
import time
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "posts.json"

# ── 5 clean categories (down from 8) ────────────────────────────────────────
CATEGORIES = [
    "Ads & Performance Marketing",
    "Automation & Workflows",
    "ABM & Pipeline",
    "Content & Campaigns",
    "Events & Field Marketing",
]

KEYWORD_MAP = {
    "Ads & Performance Marketing": [
        "ads", "advertising", "ppc", "paid", "google ads", "meta ads",
        "facebook ads", "linkedin ads", "performance", "roas", "cpm", "cpc",
        "retargeting", "programmatic", "media buying",
    ],
    "Automation & Workflows": [
        "automation", "workflow", "hubspot", "marketo", "pardot", "zapier",
        "sequence", "drip", "trigger", "email automation", "nurture",
        "crm", "salesforce", "integration",
    ],
    "ABM & Pipeline": [
        "abm", "account-based", "target account", "pipeline", "deal",
        "close", "revenue", "forecast", "opportunity", "prospecting",
        "sdr", "bdr", "cold email", "outreach", "sales enablement",
    ],
    "Content & Campaigns": [
        "content", "seo", "blog", "copywriting", "landing page",
        "social media", "copy", "campaign", "go-to-market", "gtm",
        "brand", "integrated", "omnichannel",
    ],
    "Events & Field Marketing": [
        "event", "conference", "webinar", "field marketing", "trade show",
        "booth", "sponsorship", "in-person", "virtual event", "roadshow",
    ],
}

CATEGORIZE_PROMPT = """You are a strict curator for a marketing intelligence feed. Decide if this post has a real, actionable use case of Claude AI in marketing or sales — then extract the insight.

**Keep the post ONLY if ALL are true:**
1. Claude AI (by Anthropic) is actively USED — not just mentioned in passing
2. The use is in marketing, sales, advertising, or revenue work
3. A specific task is described (e.g. "wrote cold emails", "automated ad copy")
4. A concrete outcome or clear benefit exists (e.g. "2x reply rate", "saved 4 hrs/week")

**If any criterion is missing → skip.**

Post:
Title: {title}
Content: {content}

Categories (pick exactly one if keeping):
{categories}

Reply with JSON only — no explanation, no markdown:
{{
  "skip": true/false,
  "skip_reason": "<only if skip=true: one short phrase>",
  "category": "<category or null>",
  "key_insight": "<if keeping: WHAT Claude did + WHAT the result was — one sentence, specific, no filler, do not echo the title>"
}}"""

TOP_STORIES_PROMPT = """You are curating a daily briefing for a senior marketing leader.

Below are {n} posts about Claude AI being used in marketing and sales. Pick the {k} most valuable ones based on:
- Novelty of the use case
- Actionability (can a marketer replicate this?)
- Relevance to: Ads, Automation, ABM, Pipeline, Content, Events
- Specificity of results mentioned

Posts (as JSON array with id, title, key_insight, category):
{posts_json}

Reply with JSON only — an array of the {k} best post IDs:
["id1", "id2", ...]"""


def keyword_categorize(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "Content & Campaigns"


def _get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        return None


def categorize_uncategorized() -> int:
    if not DATA_FILE.exists():
        return 0

    with open(DATA_FILE) as f:
        data = json.load(f)

    posts = data.get("posts", [])
    uncategorized = [p for p in posts if p.get("category") is None and not p.get("skip")]

    if not uncategorized:
        print("All posts already categorized.")
        return 0

    print(f"Categorizing {len(uncategorized)} posts...")
    client = _get_client()

    if not client:
        print("[warn] No Anthropic API — using keyword fallback (no quality filter).")
        for p in uncategorized:
            p["skip"] = False
            p["category"] = keyword_categorize(p["title"], p.get("summary", ""))
            p["key_insight"] = None
    else:
        categories_list = "\n".join(f"- {c}" for c in CATEGORIES)
        for i, post in enumerate(uncategorized):
            content_snippet = (post.get("summary") or post["title"])[:600]
            prompt = CATEGORIZE_PROMPT.format(
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
                        insight = parsed.get("key_insight", "").strip()
                        post["key_insight"] = insight if insight else None
                else:
                    post["skip"] = True
                    post["skip_reason"] = "parse error"
            except Exception as e:
                print(f"  [warn] API error post {i}: {e}")
                post["skip"] = False
                post["category"] = keyword_categorize(post["title"], post.get("summary", ""))
                post["key_insight"] = None

            if i < len(uncategorized) - 1:
                time.sleep(0.25)

    # Merge back
    updated = {p["id"]: p for p in uncategorized}
    for i, post in enumerate(posts):
        if post["id"] in updated:
            posts[i] = updated[post["id"]]

    kept = sum(1 for p in posts if not p.get("skip") and p.get("category"))
    skipped = sum(1 for p in posts if p.get("skip"))
    print(f"  → {kept} kept, {skipped} skipped as irrelevant.")

    data["posts"] = posts
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return len(uncategorized)


def select_top_stories(k: int = 5) -> None:
    """Use Claude to pick the k most valuable posts and mark them is_featured=True."""
    if not DATA_FILE.exists():
        return

    with open(DATA_FILE) as f:
        data = json.load(f)

    # Reset all featured flags first
    for p in data["posts"]:
        p["is_featured"] = False

    # Only consider posts with a real insight
    candidates = [p for p in data["posts"] if p.get("key_insight") and not p.get("skip")]
    if not candidates:
        # Fallback: feature the k most recent posts
        recent = sorted(
            [p for p in data["posts"] if not p.get("skip")],
            key=lambda p: p.get("fetched_at", ""),
            reverse=True,
        )[:k]
        for p in recent:
            p["is_featured"] = True
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Top stories (fallback, no insights): {len(recent)} featured.")
        return

    client = _get_client()
    if not client:
        # Fallback: feature the k most recent with insights
        recent = sorted(candidates, key=lambda p: p.get("fetched_at", ""), reverse=True)[:k]
        for p in recent:
            p["is_featured"] = True
        with open(DATA_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Top stories (no API key): {len(recent)} most recent featured.")
        return

    pool = candidates[:40]  # Send at most 40 candidates to Claude
    posts_summary = [
        {"id": p["id"], "title": p["title"], "key_insight": p["key_insight"], "category": p.get("category")}
        for p in pool
    ]

    prompt = TOP_STORIES_PROMPT.format(
        n=len(pool),
        k=k,
        posts_json=json.dumps(posts_summary, indent=2),
    )

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            featured_ids = set(json.loads(match.group()))
            count = 0
            for p in data["posts"]:
                if p["id"] in featured_ids:
                    p["is_featured"] = True
                    count += 1
            print(f"Top stories: {count} posts featured by Claude.")
        else:
            raise ValueError("No JSON array found in response")
    except Exception as e:
        print(f"  [warn] Top stories API error: {e}. Falling back to most recent.")
        recent = sorted(candidates, key=lambda p: p.get("fetched_at", ""), reverse=True)[:k]
        for p in recent:
            p["is_featured"] = True

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    categorize_uncategorized()
    select_top_stories()
