"""
Orchestrator (free tier — no API key required):
  scrape → age-purge → categorize → top stories → dashboard → email
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
    if not DATA_FILE.exists():
        return 0
    with open(DATA_FILE) as f:
        data = json.load(f)
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    before = len(data.get("posts", []))
    kept = []
    for p in data.get("posts", []):
        try:
            dt = datetime.fromisoformat(p.get("fetched_at", "").replace("Z", "+00:00"))
            if dt >= cutoff:
                kept.append(p)
        except Exception:
            kept.append(p)
    removed = before - len(kept)
    data["posts"] = kept
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    if removed:
        print(f"  Removed {removed} posts older than {MAX_AGE_DAYS} days.")
    return removed


def main() -> None:
    print("=" * 52)

    print("Step 1/5 — Scraping (Reddit · Google News · HN · Twitter)...")
    new_posts = scrape()
    existing  = load_all_posts()
    combined  = new_posts + existing
    combined  = combined[:400]
    save_posts(combined)
    print(f"  {len(new_posts)} new posts found.")

    print("\nStep 2/5 — Removing posts older than 90 days...")
    purge_old_posts()

    print("\nStep 3/5 — Categorizing + extracting insights...")
    categorize_uncategorized()

    # Cap at 150 most recent quality posts
    with open(DATA_FILE) as f:
        data = json.load(f)
    data["posts"] = sorted(
        data["posts"], key=lambda p: p.get("fetched_at", ""), reverse=True
    )[:150]
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  {len(data['posts'])} quality posts retained.")

    print("\nStep 4/5 — Selecting Top Stories...")
    select_top_stories(k=5)

    print("\nStep 5/5 — Generating dashboard + sending email digest...")
    generate_dashboard()
    send_digest()

    print("\n✓ Done.")


if __name__ == "__main__":
    main()
