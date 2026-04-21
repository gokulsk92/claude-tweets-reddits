"""
Fetches Claude AI use cases from Reddit RSS, Google News RSS, and Hacker News.
Focused on: Performance Marketing, Marketing Automation, Field/Event Marketing,
ABM, Pipeline Acceleration, Integrated Marketing.
"""

import json
import hashlib
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "posts.json"
MAX_POSTS_PER_RUN = 20

REDDIT_FEEDS = [
    # Subreddit-wide feeds for Claude/Anthropic communities
    "https://www.reddit.com/r/ClaudeAI/new/.rss",
    "https://www.reddit.com/r/anthropic/new/.rss",
    # Keyword searches across marketing/sales subreddits
    "https://www.reddit.com/r/marketing/search.rss?q=Claude+AI&sort=new&restrict_sr=1",
    "https://www.reddit.com/r/digital_marketing/search.rss?q=Claude&sort=new&restrict_sr=1",
    "https://www.reddit.com/r/sales/search.rss?q=Claude+AI&sort=new&restrict_sr=1",
    "https://www.reddit.com/r/entrepreneur/search.rss?q=Claude+AI&sort=new&restrict_sr=1",
    "https://www.reddit.com/r/PPC/search.rss?q=Claude&sort=new&restrict_sr=1",
    "https://www.reddit.com/r/startups/search.rss?q=Claude+AI&sort=new&restrict_sr=1",
    # Cross-Reddit searches by topic
    "https://www.reddit.com/search.rss?q=Claude+marketing+automation&sort=new",
    "https://www.reddit.com/search.rss?q=Claude+AI+ABM+account+based&sort=new",
    "https://www.reddit.com/search.rss?q=Claude+AI+performance+marketing+ads&sort=new",
    "https://www.reddit.com/search.rss?q=Claude+AI+sales+pipeline&sort=new",
    "https://www.reddit.com/search.rss?q=Anthropic+Claude+use+case&sort=new",
]

GOOGLE_NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=Claude+AI+marketing&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+AI+sales+automation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Anthropic+Claude+advertising+campaigns&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+AI+demand+generation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+AI+pipeline+acceleration&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+AI+ABM+account+based+marketing&hl=en-US&gl=US&ceid=US:en",
]

RELEVANCE_KEYWORDS = [
    "marketing", "sales", "ads", "advertising", "campaign", "pipeline",
    "lead", "abm", "account-based", "automation", "email", "outreach",
    "performance", "conversion", "funnel", "revenue", "crm", "demand",
    "event marketing", "field marketing", "integrated marketing",
    "content marketing", "growth", "b2b", "saas", "agency", "use case",
    "case study", "workflow", "productivity", "roi", "metrics",
]

HEADERS = {
    "User-Agent": "claude-curator/1.0 (personal research tool)"
}


def fetch_url(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [warn] Failed to fetch {url}: {e}")
        return None


def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    # Must mention Claude or Anthropic
    if "claude" not in text and "anthropic" not in text:
        return False
    # Must touch at least one marketing/sales keyword
    return any(kw in text for kw in RELEVANCE_KEYWORDS)


def clean_html(raw: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", raw)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:800]


def parse_reddit_rss(xml_text: str, source_label: str) -> list[dict]:
    posts = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns)
        for entry in entries:
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            content_el = entry.find("atom:content", ns)
            updated_el = entry.find("atom:updated", ns)

            title = title_el.text if title_el is not None else ""
            url = link_el.get("href", "") if link_el is not None else ""
            summary = clean_html(content_el.text or "") if content_el is not None else ""
            date_str = updated_el.text if updated_el is not None else ""

            if not title or not url:
                continue
            if not is_relevant(title, summary):
                continue

            posts.append({
                "id": make_id(url),
                "title": title.strip(),
                "url": url,
                "summary": summary,
                "source": "Reddit",
                "source_label": source_label,
                "date": date_str,
                "category": None,
                "key_insight": None,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    except ET.ParseError as e:
        print(f"  [warn] XML parse error for {source_label}: {e}")
    return posts


def parse_rss(xml_text: str, source: str) -> list[dict]:
    posts = []
    try:
        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return posts
        items = channel.findall("item")
        for item in items:
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pubdate_el = item.find("pubDate")

            title = title_el.text if title_el is not None else ""
            url = link_el.text if link_el is not None else ""
            summary = clean_html(desc_el.text or "") if desc_el is not None else ""
            date_str = pubdate_el.text if pubdate_el is not None else ""

            if not title or not url:
                continue
            if not is_relevant(title, summary):
                continue

            posts.append({
                "id": make_id(url),
                "title": title.strip(),
                "url": url,
                "summary": summary,
                "source": source,
                "source_label": source,
                "date": date_str,
                "category": None,
                "key_insight": None,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            })
    except ET.ParseError as e:
        print(f"  [warn] XML parse error for {source}: {e}")
    return posts


def fetch_hacker_news() -> list[dict]:
    posts = []
    queries = [
        "Claude marketing",
        "Claude AI sales",
        "Anthropic Claude automation",
    ]
    for q in queries:
        encoded = urllib.parse.quote(q)
        url = f"https://hn.algolia.com/api/v1/search?query={encoded}&tags=story&hitsPerPage=10"
        raw = fetch_url(url)
        if not raw:
            continue
        try:
            data = json.loads(raw)
            for hit in data.get("hits", []):
                title = hit.get("title", "")
                hn_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                summary = hit.get("story_text") or ""
                if summary:
                    summary = clean_html(summary)
                date_str = hit.get("created_at", "")

                if not is_relevant(title, summary):
                    continue

                posts.append({
                    "id": make_id(hn_url),
                    "title": title,
                    "url": hn_url,
                    "summary": summary[:800],
                    "source": "Hacker News",
                    "source_label": "Hacker News",
                    "date": date_str,
                    "category": None,
                    "key_insight": None,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })
        except json.JSONDecodeError:
            pass
    return posts


def load_existing_ids() -> set[str]:
    if not DATA_FILE.exists():
        return set()
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        return {p["id"] for p in data.get("posts", [])}
    except Exception:
        return set()


def load_all_posts() -> list[dict]:
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        return data.get("posts", [])
    except Exception:
        return []


def save_posts(posts: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total": len(posts),
        "posts": posts,
    }
    with open(DATA_FILE, "w") as f:
        json.dump(payload, f, indent=2)


def scrape() -> list[dict]:
    existing_ids = load_existing_ids()
    new_posts: list[dict] = []

    print("Fetching Reddit RSS feeds...")
    for feed_url in REDDIT_FEEDS:
        label = feed_url.split("reddit.com/")[1].split("/")[0] if "reddit.com/" in feed_url else "reddit"
        xml = fetch_url(feed_url)
        if xml:
            posts = parse_reddit_rss(xml, label)
            for p in posts:
                if p["id"] not in existing_ids:
                    new_posts.append(p)
                    existing_ids.add(p["id"])

    print("Fetching Google News RSS feeds...")
    for feed_url in GOOGLE_NEWS_FEEDS:
        xml = fetch_url(feed_url)
        if xml:
            posts = parse_rss(xml, "Google News")
            for p in posts:
                if p["id"] not in existing_ids:
                    new_posts.append(p)
                    existing_ids.add(p["id"])

    print("Fetching Hacker News...")
    hn_posts = fetch_hacker_news()
    for p in hn_posts:
        if p["id"] not in existing_ids:
            new_posts.append(p)
            existing_ids.add(p["id"])

    print(f"Found {len(new_posts)} new posts.")
    return new_posts


if __name__ == "__main__":
    new_posts = scrape()
    existing = load_all_posts()
    # Prepend new posts, keep latest 200 total
    all_posts = new_posts + existing
    all_posts = all_posts[:200]
    save_posts(all_posts)
    print(f"Saved {len(all_posts)} total posts.")
