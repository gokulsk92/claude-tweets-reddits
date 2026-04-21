"""
Orchestrator: runs scraper → categorizer → dashboard generator → email digest.
Called by GitHub Actions daily.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from scraper import scrape, load_all_posts, save_posts
from categorizer import categorize_uncategorized
from dashboard import generate as generate_dashboard
from email_digest import send_digest


def main() -> None:
    print("=" * 50)
    print("Step 1/4: Scraping new posts...")
    new_posts = scrape()

    existing = load_all_posts()
    all_posts = new_posts + existing
    all_posts = all_posts[:200]
    save_posts(all_posts)

    print(f"\nStep 2/4: Categorizing {len([p for p in all_posts if not p.get('category')])} uncategorized posts...")
    categorize_uncategorized()

    print("\nStep 3/4: Generating dashboard...")
    generate_dashboard()

    print("\nStep 4/4: Sending email digest...")
    send_digest()

    print("\nDone!")


if __name__ == "__main__":
    main()
