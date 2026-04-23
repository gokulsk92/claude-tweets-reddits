"""
Orchestrator: scrape → age-purge → categorize → skip-purge → top stories → dashboard → email.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scraper import scrape, load_all_posts, save_posts
from categorizer import categorize_uncategorized, select_top_stories
from dashboard import generate as generate_dashboard
from email_digest import send_digest

DATA_FILE = Path(__file__).parent.parent / "data" / "posts.json"
MAX_AGE_DAYS = 90


def purge_old_posts() -> int:
    """Remove posts older than MAX_AGE_DAYS from the stored dataset."""
    if not DATA_FILE.exists():
        return 0
    with open(DATA_FILE) as f:
        data = json.load(f)
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    before = len(data.get("posts", []))
    kept = []
    for p in data.get("posts", []):
        fetched = p.get("fetched_at", "")
        try:
            dt = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
            if dt >= cutoff:
                kept.append(p)
        except Exception:
            kept.append(p)  # Unknown date — keep it
    removed = before - len(kept)
    data["posts"] = kept
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    if removed:
        print(f"  Removed {removed} posts older than {MAX_AGE_DAYS} days.")
    return removed


def purge_skipped() -> int:
    """Remove posts the AI marked as irrelevant."""
    if not DATA_FILE.exists():
        return 0
    with open(DATA_FILE) as f:
        data = json.load(f)
    before = len(data.get("posts", []))
    data["posts"] = [p for p in data.get("posts", []) if not p.get("skip")]
    removed = before - len(data["posts"])
    if removed:
        print(f"  Purged {removed} irrelevant posts.")
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return removed


def main() -> None:
    print("=" * 52)

    print("Step 1/6 — Scraping new posts...")
    new_posts = scrape()
    existing  = load_all_posts()
    all_posts = new_posts + existing
    all_posts = all_posts[:400]
    save_posts(all_posts)

    print("\nStep 2/6 — Removing posts older than 90 days...")
    purge_old_posts()

    print("\nStep 3/6 — AI relevance filter + categorization...")
    categorize_uncategorized()

    print("\nStep 4/6 — Purging irrelevant posts...")
    purge_skipped()

    # Final cap: keep the 150 most recent quality posts
    with open(DATA_FILE) as f:
        data = json.load(f)
    data["posts"] = sorted(
        data["posts"], key=lambda p: p.get("fetched_at", ""), reverse=True
    )[:150]
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  {len(data['posts'])} quality posts retained.")

    print("\nStep 5/6 — Selecting Top Stories...")
    select_top_stories(k=5)

    print("\nStep 6/6 — Generating dashboard + sending email...")
    generate_dashboard()
    send_digest()

    print("\n✓ Done.")


if __name__ == "__main__":
    main()
