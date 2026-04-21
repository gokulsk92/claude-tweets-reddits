"""
Generates a clean HTML dashboard from posts.json and writes it to docs/index.html
(served via GitHub Pages).
"""

import json
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "posts.json"
DOCS_DIR = Path(__file__).parent.parent / "docs"

CATEGORY_COLORS = {
    "Performance Marketing & Ads": "#e74c3c",
    "Marketing Automation": "#9b59b6",
    "Field & Event Marketing": "#e67e22",
    "ABM (Account-Based Marketing)": "#2980b9",
    "Pipeline Acceleration": "#27ae60",
    "Integrated Marketing": "#16a085",
    "Content & SEO": "#f39c12",
    "Sales Enablement": "#2c3e50",
    "General / Other": "#95a5a6",
}

SOURCE_ICONS = {
    "Reddit": "🟠",
    "Google News": "🔵",
    "Hacker News": "🟡",
}


def format_date(date_str: str) -> str:
    if not date_str:
        return "Unknown date"
    for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"]:
        try:
            dt = datetime.strptime(date_str[:25], fmt[:len(date_str[:25])])
            return dt.strftime("%b %d, %Y")
        except ValueError:
            continue
    return date_str[:10]


def build_html(posts: list[dict], last_updated: str) -> str:
    all_categories = sorted(set(p.get("category") or "General / Other" for p in posts))

    # Build filter buttons
    filter_buttons = '<button class="filter-btn active" onclick="filterPosts(\'all\')">All</button>\n'
    for cat in all_categories:
        color = CATEGORY_COLORS.get(cat, "#95a5a6")
        safe_cat = cat.replace("'", "\\'").replace("(", "\\(").replace(")", "\\)")
        filter_buttons += f'<button class="filter-btn" onclick="filterPosts(\'{safe_cat}\')" style="border-color:{color}">{cat}</button>\n'

    # Build post cards
    cards_html = ""
    for post in posts:
        cat = post.get("category") or "General / Other"
        color = CATEGORY_COLORS.get(cat, "#95a5a6")
        source = post.get("source", "Unknown")
        icon = SOURCE_ICONS.get(source, "📰")
        insight = post.get("key_insight") or ""
        summary = post.get("summary", "")[:300]
        date_display = format_date(post.get("date", ""))
        url = post.get("url", "#")
        title = post.get("title", "Untitled")
        safe_cat = cat.replace("'", "\\'")

        cards_html += f"""
        <div class="card" data-category="{safe_cat}">
            <div class="card-header">
                <span class="badge" style="background:{color}">{cat}</span>
                <span class="source">{icon} {source} &middot; {date_display}</span>
            </div>
            <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
            {"<div class='insight'>💡 " + insight + "</div>" if insight else ""}
            {"<p class='summary'>" + summary + ("..." if len(post.get("summary","")) > 300 else "") + "</p>" if summary else ""}
            <a href="{url}" target="_blank" rel="noopener" class="read-link">Read full post →</a>
        </div>"""

    updated_display = datetime.fromisoformat(last_updated.replace("Z", "+00:00")).strftime("%B %d, %Y at %H:%M UTC") if last_updated else "Unknown"
    total = len(posts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Claude AI — Marketing & Sales Use Cases</title>
<style>
  :root {{
    --bg: #0f0f11;
    --surface: #1a1a1f;
    --surface2: #222228;
    --border: #2e2e38;
    --text: #e8e8f0;
    --text2: #9999b0;
    --accent: #7c5cfc;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}

  header {{ background: var(--surface); border-bottom: 1px solid var(--border); padding: 24px 32px; }}
  .header-inner {{ max-width: 1200px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }}
  .logo {{ font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }}
  .logo span {{ color: var(--accent); }}
  .meta {{ font-size: 13px; color: var(--text2); }}

  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px; }}

  .stats {{ display: flex; gap: 24px; margin-bottom: 28px; flex-wrap: wrap; }}
  .stat {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 24px; min-width: 140px; }}
  .stat-num {{ font-size: 28px; font-weight: 700; color: var(--accent); }}
  .stat-label {{ font-size: 12px; color: var(--text2); margin-top: 2px; }}

  .filters {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 28px; }}
  .filter-btn {{
    background: var(--surface2); border: 1px solid var(--border); color: var(--text2);
    padding: 7px 14px; border-radius: 20px; cursor: pointer; font-size: 13px;
    transition: all 0.15s;
  }}
  .filter-btn:hover {{ color: var(--text); border-color: var(--accent); }}
  .filter-btn.active {{ background: var(--accent); color: white; border-color: var(--accent); }}

  .search-bar {{ margin-bottom: 24px; }}
  .search-bar input {{
    width: 100%; max-width: 500px; background: var(--surface); border: 1px solid var(--border);
    color: var(--text); padding: 10px 16px; border-radius: 8px; font-size: 14px; outline: none;
  }}
  .search-bar input:focus {{ border-color: var(--accent); }}

  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 20px; }}

  .card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    padding: 20px; transition: border-color 0.15s, transform 0.15s;
  }}
  .card:hover {{ border-color: var(--accent); transform: translateY(-2px); }}
  .card.hidden {{ display: none; }}

  .card-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 6px; }}
  .badge {{ font-size: 11px; font-weight: 600; color: white; padding: 3px 10px; border-radius: 12px; white-space: nowrap; }}
  .source {{ font-size: 12px; color: var(--text2); }}

  .card-title {{ font-size: 15px; font-weight: 600; line-height: 1.4; margin-bottom: 10px; }}
  .card-title a {{ color: var(--text); text-decoration: none; }}
  .card-title a:hover {{ color: var(--accent); }}

  .insight {{ background: var(--surface2); border-left: 3px solid var(--accent); padding: 8px 12px; border-radius: 0 6px 6px 0; font-size: 13px; color: var(--text); margin-bottom: 10px; line-height: 1.5; }}
  .summary {{ font-size: 13px; color: var(--text2); line-height: 1.6; margin-bottom: 12px; }}
  .read-link {{ font-size: 13px; color: var(--accent); text-decoration: none; font-weight: 500; }}
  .read-link:hover {{ text-decoration: underline; }}

  .no-results {{ text-align: center; color: var(--text2); padding: 60px 0; font-size: 15px; display: none; }}

  footer {{ text-align: center; padding: 32px; color: var(--text2); font-size: 13px; border-top: 1px solid var(--border); margin-top: 40px; }}

  @media (max-width: 640px) {{
    .container {{ padding: 16px; }}
    .grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<header>
  <div class="header-inner">
    <div class="logo">Claude AI <span>Marketing & Sales</span> Insights</div>
    <div class="meta">Last updated: {updated_display}</div>
  </div>
</header>

<div class="container">

  <div class="stats">
    <div class="stat">
      <div class="stat-num">{total}</div>
      <div class="stat-label">Total Posts</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(all_categories)}</div>
      <div class="stat-label">Categories</div>
    </div>
    <div class="stat">
      <div class="stat-num">Daily</div>
      <div class="stat-label">Update Frequency</div>
    </div>
  </div>

  <div class="search-bar">
    <input type="text" id="searchInput" placeholder="Search posts..." oninput="searchPosts()">
  </div>

  <div class="filters">
    {filter_buttons}
  </div>

  <div class="grid" id="postsGrid">
    {cards_html}
  </div>

  <div class="no-results" id="noResults">No posts found for this filter.</div>

</div>

<footer>
  Auto-curated daily from Reddit, Google News & Hacker News &middot; Powered by Claude AI &middot;
  <a href="https://github.com/gokulsk92/claude-tweets-reddits" style="color:var(--accent)">View on GitHub</a>
</footer>

<script>
  let activeCategory = 'all';
  let searchQuery = '';

  function filterPosts(category) {{
    activeCategory = category;
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');
    applyFilters();
  }}

  function searchPosts() {{
    searchQuery = document.getElementById('searchInput').value.toLowerCase();
    applyFilters();
  }}

  function applyFilters() {{
    const cards = document.querySelectorAll('.card');
    let visible = 0;
    cards.forEach(card => {{
      const cat = card.dataset.category || '';
      const text = card.textContent.toLowerCase();
      const catMatch = activeCategory === 'all' || cat === activeCategory;
      const searchMatch = !searchQuery || text.includes(searchQuery);
      if (catMatch && searchMatch) {{
        card.classList.remove('hidden');
        visible++;
      }} else {{
        card.classList.add('hidden');
      }}
    }});
    document.getElementById('noResults').style.display = visible === 0 ? 'block' : 'none';
  }}
</script>

</body>
</html>"""


def generate() -> None:
    if not DATA_FILE.exists():
        print("No data file yet. Run scraper first.")
        # Generate empty dashboard
        DOCS_DIR.mkdir(exist_ok=True)
        with open(DOCS_DIR / "index.html", "w") as f:
            f.write(build_html([], datetime.utcnow().isoformat()))
        return

    with open(DATA_FILE) as f:
        data = json.load(f)

    posts = data.get("posts", [])
    last_updated = data.get("last_updated", "")

    DOCS_DIR.mkdir(exist_ok=True)
    html = build_html(posts, last_updated)
    with open(DOCS_DIR / "index.html", "w") as f:
        f.write(html)

    print(f"Dashboard generated: {len(posts)} posts → docs/index.html")


if __name__ == "__main__":
    generate()
