"""
Fetches Claude AI use cases from Reddit RSS, Google News RSS, Hacker News, and Twitter (via Nitter).
Focused on: Performance Marketing, Marketing Automation, Field/Event Marketing,
ABM, Pipeline Acceleration, Integrated Marketing.
"""

import json
import hashlib
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

MAX_AGE_DAYS = 90   # Discard anything older than this

DATA_FILE = Path(__file__).parent.parent / "data" / "posts.json"

REDDIT_FEEDS = [
    "https://www.reddit.com/r/ClaudeAI/new/.rss",
    "https://www.reddit.com/r/anthropic/new/.rss",
    "https://www.reddit.com/r/marketing/search.rss?q=Claude+AI&sort=new&restrict_sr=1",
    "https://www.reddit.com/r/digital_marketing/search.rss?q=Claude+AI&sort=new&restrict_sr=1",
    "https://www.reddit.com/r/sales/search.rss?q=Claude+AI&sort=new&restrict_sr=1",
    "https://www.reddit.com/r/entrepreneur/search.rss?q=Claude+AI&sort=new&restrict_sr=1",
    "https://www.reddit.com/r/PPC/search.rss?q=Claude+AI&sort=new&restrict_sr=1",
    "https://www.reddit.com/r/startups/search.rss?q=Claude+AI&sort=new&restrict_sr=1",
    "https://www.reddit.com/search.rss?q=Claude+AI+marketing+automation&sort=new",
    "https://www.reddit.com/search.rss?q=Claude+AI+ABM+account+based&sort=new",
    "https://www.reddit.com/search.rss?q=Claude+AI+performance+marketing&sort=new",
    "https://www.reddit.com/search.rss?q=Claude+AI+sales+pipeline&sort=new",
    "https://www.reddit.com/search.rss?q=Anthropic+Claude+marketing+use+case&sort=new",
]

GOOGLE_NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=Claude+AI+marketing&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+AI+sales+automation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Anthropic+Claude+advertising&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+AI+demand+generation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+AI+ABM+account+based+marketing&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Claude+AI+pipeline+acceleration&hl=en-US&gl=US&ceid=US:en",
]

# Nitter = free, open-source Twitter mirror with RSS support.
# Tries each instance in order; uses the first one that responds.
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.lunar.icu",
]

TWITTER_SEARCHES = [
    "Claude AI marketing",
    "Claude AI sales automation",
    "Anthropic Claude marketing use case",
    "Claude AI ABM pipeline",
    "Claude AI ads performance marketing",
    "Claude AI marketing automation",
]

MARKETING_KEYWORDS = [
    "marketing", "sales", "ads", "advertising", "campaign", "pipeline",
    "lead generation", "abm", "account-based", "automation", "email marketing",
    "outreach", "performance marketing", "conversion", "funnel", "revenue",
    "crm", "demand generation", "event marketing", "field marketing",
    "integrated marketing", "content marketing", "growth", "b2b",
    "use case", "case study", "roi", "cold email", "prospecting",
    "sdr", "bdr", "go-to-market", "gtm", "brand campaign",
]

# Strong Claude-AI signals (disambiguates from the name "Claude")
CLAUDE_AI_SIGNALS = [
    "claude ai", "claude 3", "claude 4", "claude opus", "claude sonnet",
    "claude haiku", "anthropic claude", "anthropic's claude",
    "claude.ai", "@anthropic",
]

HEADERS = {
    "User-Agent": "claude-curator/1.0 (personal research tool)"
}


def fetch_url(url: str, timeout: int = 15) -> str | None:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  [warn] Failed to fetch {url[:80]}: {e}")
        return None


def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def parse_date(date_str: str) -> datetime | None:
    """Parse various date formats into UTC datetime. Returns None on failure."""
    if not date_str:
        return None
    for fmt in [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]:
        try:
            return datetime.strptime(date_str[:len(fmt) + 5].strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    # ISO fallback
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return None


def is_too_old(date_str: str) -> bool:
    """Return True if the post is older than MAX_AGE_DAYS."""
    dt = parse_date(date_str)
    if dt is None:
        return False  # Unknown date — keep it
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    return dt < cutoff


def is_relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()

    # Must have a strong Claude AI signal OR plain "claude"/"anthropic" with stricter marketing check
    has_strong_claude = any(sig in text for sig in CLAUDE_AI_SIGNALS)
    has_plain_claude = "claude" in text or "anthropic" in text

    if not has_plain_claude:
        return False

    # Count how many distinct marketing keywords appear
    marketing_hits = sum(1 for kw in MARKETING_KEYWORDS if kw in text)

    if has_strong_claude:
        # Strong Claude signal: only need 1 marketing keyword
        return marketing_hits >= 1
    else:
        # Weak signal ("claude" could be a person's name): require 2+ marketing keywords
        return marketing_hits >= 2


def clean_html(raw: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", raw)
    clean = re.sub(r"&[a-z]+;", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:1000]


def parse_reddit_rss(xml_text: str, source_label: str) -> list[dict]:
    posts = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            content_el = entry.find("atom:content", ns)
            updated_el = entry.find("atom:updated", ns)

            title = (title_el.text or "").strip()
            url = link_el.get("href", "") if link_el is not None else ""
            summary = clean_html(content_el.text or "") if content_el is not None else ""
            date_str = updated_el.text if updated_el is not None else ""

            if not title or not url:
                continue
            if is_too_old(date_str):
                continue
            if not is_relevant(title, summary):
                continue

            posts.append({
                "id": make_id(url),
                "title": title,
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
        for item in channel.findall("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            pubdate_el = item.find("pubDate")

            title = (title_el.text or "").strip()
            url = (link_el.text or "").strip()
            summary = clean_html(desc_el.text or "") if desc_el is not None else ""
            date_str = pubdate_el.text if pubdate_el is not None else ""

            if not title or not url:
                continue
            if is_too_old(date_str):
                continue
            if not is_relevant(title, summary):
                continue

            posts.append({
                "id": make_id(url),
                "title": title,
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


def find_working_nitter() -> str | None:
    """Return the first nitter instance that responds successfully."""
    for instance in NITTER_INSTANCES:
        test_url = f"{instance}/search/rss?q=Claude+AI+marketing&f=tweets"
        result = fetch_url(test_url, timeout=8)
        if result and "<item>" in result:
            print(f"  Using nitter instance: {instance}")
            return instance
    return None


def fetch_twitter_nitter() -> list[dict]:
    posts = []
    instance = find_working_nitter()
    if not instance:
        print("  [warn] No nitter instance available. Skipping Twitter.")
        return posts

    for query in TWITTER_SEARCHES:
        encoded = urllib.parse.quote(query)
        url = f"{instance}/search/rss?q={encoded}&f=tweets"
        xml = fetch_url(url, timeout=10)
        if not xml:
            continue

        try:
            root = ET.fromstring(xml)
            channel = root.find("channel")
            if channel is None:
                continue
            for item in channel.findall("item"):
                title_el = item.find("title")
                link_el = item.find("link")
                desc_el = item.find("description")
                pubdate_el = item.find("pubDate")

                title = (title_el.text or "").strip()
                url_raw = (link_el.text or "").strip()
                summary = clean_html(desc_el.text or "") if desc_el is not None else ""
                date_str = pubdate_el.text if pubdate_el is not None else ""

                # Convert nitter URL to twitter.com URL
                tweet_url = url_raw.replace(instance.replace("https://", ""), "twitter.com")

                if not title or not url_raw:
                    continue
                if is_too_old(date_str):
                    continue
                # For tweets, title IS the tweet text — check full text
                if not is_relevant(title, summary):
                    continue

                posts.append({
                    "id": make_id(url_raw),
                    "title": title[:280],
                    "url": tweet_url,
                    "summary": summary,
                    "source": "Twitter",
                    "source_label": "Twitter",
                    "date": date_str,
                    "category": None,
                    "key_insight": None,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                })
        except ET.ParseError:
            pass

    return posts


def fetch_hacker_news() -> list[dict]:
    posts = []
    queries = [
        "Claude marketing",
        "Claude AI sales automation",
        "Anthropic Claude marketing",
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
                summary = clean_html(hit.get("story_text") or "")
                date_str = hit.get("created_at", "")

                if is_too_old(date_str):
                    continue
                if not is_relevant(title, summary):
                    continue

                posts.append({
                    "id": make_id(hn_url),
                    "title": title,
                    "url": hn_url,
                    "summary": summary[:1000],
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

    def add_if_new(posts: list[dict]) -> None:
        for p in posts:
            if p["id"] not in existing_ids:
                new_posts.append(p)
                existing_ids.add(p["id"])

    print("Fetching Reddit RSS feeds...")
    for feed_url in REDDIT_FEEDS:
        label = feed_url.split("reddit.com/")[1].split("/")[0] if "reddit.com/" in feed_url else "reddit"
        xml = fetch_url(feed_url)
        if xml:
            add_if_new(parse_reddit_rss(xml, label))

    print("Fetching Google News RSS feeds...")
    for feed_url in GOOGLE_NEWS_FEEDS:
        xml = fetch_url(feed_url)
        if xml:
            add_if_new(parse_rss(xml, "Google News"))

    print("Fetching Hacker News...")
    add_if_new(fetch_hacker_news())

    print("Fetching Twitter via Nitter...")
    add_if_new(fetch_twitter_nitter())

    print(f"Found {len(new_posts)} new posts after relevance filtering.")
    return new_posts


if __name__ == "__main__":
    new_posts = scrape()
    existing = load_all_posts()
    all_posts = new_posts + existing
    all_posts = all_posts[:200]
    save_posts(all_posts)
    print(f"Saved {len(all_posts)} total posts.")
