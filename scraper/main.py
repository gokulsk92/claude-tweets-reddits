"""
Orchestrator: scrape → categorize (with AI skip filter) → save only relevant posts → dashboard → email.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json
from scraper import scrape, load_all_posts, save_posts
from categorizer import categorize_uncategorized
from dashboard import generate as generate_dashboard
from email_digest import send_digest

DATA_FILE = Path(__file__).parent.parent / "data" / "posts.json"


def purge_skipped() -> int:
    """Remove posts marked skip=True from the data file."""
    if not DATA_FILE.exists():
        return 0
    with open(DATA_FILE) as f:
        data = json.load(f)
    before = len(data.get("posts", []))
    data["posts"] = [p for p in data.get("posts", []) if not p.get("skip")]
    after = len(data["posts"])
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    removed = before - after
    if removed:
        print(f"Purged {removed} irrelevant posts.")
    return removed


def main() -> None:
    print("=" * 50)
    print("Step 1/5: Scraping new posts...")
    new_posts = scrape()

    existing = load_all_posts()
    all_posts = new_posts + existing
    # Keep max 300 before filtering (filtered set will be smaller)
    all_posts = all_posts[:300]
    save_posts(all_posts)

    print(f"\nStep 2/5: AI relevance filtering + categorization...")
    categorize_uncategorized()

    print(f"\nStep 3/5: Purging irrelevant posts...")
    purge_skipped()

    # Reload and cap at 150 quality posts
    with open(DATA_FILE) as f:
        data = json.load(f)
    data["posts"] = data["posts"][:150]
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Kept {len(data['posts'])} quality posts total.")

    print("\nStep 4/5: Generating dashboard...")
    generate_dashboard()

    print("\nStep 5/5: Sending email digest...")
    send_digest()

    print("\nDone!")


if __name__ == "__main__":
    main()
