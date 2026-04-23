"""
Free-tier categorizer — no API needed.
1. Keyword-based category assignment
2. Insight extraction: finds the sentence in the summary that mentions Claude
3. Top Stories: scored by marketing keyword density + recency
"""

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "posts.json"

CATEGORIES = [
    "Ads & Performance Marketing",
    "Automation & Workflows",
    "ABM & Pipeline",
    "Content & Campaigns",
    "Events & Field Marketing",
]

KEYWORD_MAP = {
    "Ads & Performance Marketing": [
        "ads", "advertising", "ppc", "paid search", "google ads", "meta ads",
        "facebook ads", "linkedin ads", "performance marketing", "roas", "cpm",
        "cpc", "retargeting", "programmatic", "media buying", "ad copy",
        "ad creative", "conversion rate",
    ],
    "Automation & Workflows": [
        "automation", "workflow", "hubspot", "marketo", "pardot", "zapier",
        "email sequence", "drip campaign", "trigger", "email automation",
        "lead nurture", "crm", "salesforce", "integration", "automate",
    ],
    "ABM & Pipeline": [
        "abm", "account-based", "target account", "pipeline", "deal velocity",
        "close rate", "revenue", "sales forecast", "crm", "opportunity",
        "prospecting", "sdr", "bdr", "cold email", "outreach", "sales cycle",
        "sales enablement", "playbook",
    ],
    "Content & Campaigns": [
        "content marketing", "seo", "blog post", "copywriting", "landing page",
        "social media", "ad copy", "campaign", "go-to-market", "gtm",
        "brand", "integrated campaign", "omnichannel", "content strategy",
        "email marketing", "newsletter",
    ],
    "Events & Field Marketing": [
        "event", "conference", "webinar", "field marketing", "trade show",
        "booth", "sponsorship", "in-person", "virtual event", "roadshow",
        "event marketing",
    ],
}

# Words that boost relevance score — specific use-case signals
USECASE_SIGNALS = [
    "use case", "case study", "how i", "how we", "i used", "we used",
    "built with", "using claude", "claude helped", "saved", "reduced",
    "increased", "improved", "automated", "generated", "wrote",
    "created", "deployed", "launched", "results", "roi", "%", "x faster",
    "hours saved", "per week", "per month",
]

CLAUDE_TERMS = [
    "claude", "claude ai", "claude 3", "claude 4", "anthropic",
    "claude opus", "claude sonnet", "claude haiku",
]


# ── Category assignment ───────────────────────────────────────────────────────

def assign_category(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, keywords in KEYWORD_MAP.items():
        for kw in keywords:
            if kw in text:
                scores[cat] += 1
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] > 0 else "Content & Campaigns"


# ── Insight extraction ────────────────────────────────────────────────────────

def extract_insight(title: str, summary: str) -> str | None:
    """
    Find the most informative sentence from title+summary:
    1. Prefer sentences that mention Claude AND a use-case signal
    2. Fall back to any sentence mentioning Claude
    3. Fall back to None
    """
    # Combine and split into sentences
    full_text = f"{title}. {summary}" if summary else title
    sentences = re.split(r'(?<=[.!?])\s+', full_text)

    best_score = -1
    best_sentence = None

    for sent in sentences:
        s = sent.lower().strip()
        if len(s) < 20:
            continue

        has_claude = any(term in s for term in CLAUDE_TERMS)
        signal_count = sum(1 for sig in USECASE_SIGNALS if sig in s)

        if has_claude and signal_count > 0:
            score = signal_count + len(s.split()) / 50  # slightly favour longer sentences
            if score > best_score:
                best_score = score
                best_sentence = sent.strip().rstrip(".")

    if best_sentence:
        # Cap length
        return best_sentence[:200]

    # Fallback: first sentence that mentions Claude
    for sent in sentences:
        if any(term in sent.lower() for term in CLAUDE_TERMS) and len(sent) > 20:
            return sent.strip()[:200]

    return None


# ── Top Stories scoring ───────────────────────────────────────────────────────

def score_post(post: dict) -> float:
    """Higher = more likely to be a top story."""
    title   = post.get("title", "")
    summary = post.get("summary", "")
    text    = (title + " " + summary).lower()
    score   = 0.0

    # Use-case signals
    score += sum(2.0 for sig in USECASE_SIGNALS if sig in text)

    # Marketing keyword density
    all_kw = [kw for kws in KEYWORD_MAP.values() for kw in kws]
    score += sum(0.5 for kw in all_kw if kw in text)

    # Has a real insight
    if post.get("key_insight"):
        score += 3.0

    # Recency bonus (posts in last 7 days get +5)
    fetched = post.get("fetched_at", "")
    if fetched:
        try:
            dt = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - dt).days
            if age_days <= 7:
                score += 5.0
            elif age_days <= 30:
                score += 2.0
        except Exception:
            pass

    # Source preference (news articles tend to have more substance)
    if post.get("source") == "Google News":
        score += 1.0

    return score


# ── Main public functions ─────────────────────────────────────────────────────

def categorize_uncategorized() -> int:
    if not DATA_FILE.exists():
        return 0
    with open(DATA_FILE) as f:
        data = json.load(f)

    posts = data.get("posts", [])
    to_process = [p for p in posts if p.get("category") is None and not p.get("skip")]

    if not to_process:
        print("All posts already categorized.")
        return 0

    print(f"Categorizing {len(to_process)} posts (keyword mode)...")
    for post in to_process:
        title   = post.get("title", "")
        summary = post.get("summary", "")
        post["skip"]        = False
        post["category"]    = assign_category(title, summary)
        post["key_insight"] = extract_insight(title, summary)

    # Merge back
    updated = {p["id"]: p for p in to_process}
    for i, p in enumerate(posts):
        if p["id"] in updated:
            posts[i] = updated[p["id"]]

    with_insight = sum(1 for p in posts if p.get("key_insight"))
    print(f"  → {len(to_process)} categorized, {with_insight} with extracted insights.")

    data["posts"] = posts
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return len(to_process)


def select_top_stories(k: int = 5) -> None:
    """Score every post and mark the top k as is_featured=True."""
    if not DATA_FILE.exists():
        return
    with open(DATA_FILE) as f:
        data = json.load(f)

    candidates = [p for p in data["posts"] if not p.get("skip") and p.get("category")]
    for p in data["posts"]:
        p["is_featured"] = False

    ranked = sorted(candidates, key=score_post, reverse=True)
    for p in ranked[:k]:
        p["is_featured"] = True

    print(f"Top {k} stories selected by relevance score.")
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


if __name__ == "__main__":
    categorize_uncategorized()
    select_top_stories()
