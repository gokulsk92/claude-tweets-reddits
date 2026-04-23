"""
Generates docs/index.html from posts.json.
Layout:
  1. Header + stats bar
  2. ⭐ Top Stories section (is_featured=True posts)
  3. Filter tabs (5 categories)
  4. All-posts grid
"""

import json
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "posts.json"
DOCS_DIR  = Path(__file__).parent.parent / "docs"

# 5 categories → colour
CAT_COLOR = {
    "Ads & Performance Marketing":  "#e74c3c",
    "Automation & Workflows":       "#9b59b6",
    "ABM & Pipeline":               "#2980b9",
    "Content & Campaigns":          "#f39c12",
    "Events & Field Marketing":     "#27ae60",
}
DEFAULT_COLOR = "#7c5cfc"

SOURCE_ICON = {"Reddit": "🟠", "Google News": "🔵", "Hacker News": "🟡", "Twitter": "🐦"}


def fmt_date(s: str) -> str:
    if not s:
        return ""
    for fmt in ["%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
                "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT"]:
        try:
            return datetime.strptime(s[:25], fmt[:len(s[:25])]).strftime("%b %d, %Y")
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%b %d, %Y")
    except Exception:
        return s[:10]


def card_html(p: dict, featured: bool = False) -> str:
    cat    = p.get("category") or "Content & Campaigns"
    color  = CAT_COLOR.get(cat, DEFAULT_COLOR)
    src    = p.get("source", "")
    icon   = SOURCE_ICON.get(src, "📰")
    date   = fmt_date(p.get("date", ""))
    title  = p.get("title", "Untitled")
    url    = p.get("url", "#")
    insight = p.get("key_insight") or ""
    summary = (p.get("summary") or "")[:280]
    safe_cat = cat.replace("'", "\\'")
    star   = "⭐ " if featured else ""

    return f"""<div class="card{'  card--featured' if featured else ''}" data-category="{safe_cat}">
  <div class="card-header">
    <span class="badge" style="background:{color}">{star}{cat}</span>
    <span class="source">{icon} {src}&nbsp;·&nbsp;{date}</span>
  </div>
  <h3 class="card-title"><a href="{url}" target="_blank" rel="noopener">{title}</a></h3>
  {"<div class='insight'>💡 " + insight + "</div>" if insight else ""}
  {"<p class='summary'>" + summary + ("…" if len(p.get('summary',''))>280 else "") + "</p>" if summary else ""}
  <a href="{url}" target="_blank" rel="noopener" class="read-link">Read full post →</a>
</div>"""


def build_html(posts: list[dict], last_updated: str) -> str:
    featured  = [p for p in posts if p.get("is_featured") and not p.get("skip")]
    regular   = [p for p in posts if not p.get("is_featured") and not p.get("skip")]
    all_cats  = sorted({p.get("category") or "" for p in posts if p.get("category")})

    updated_display = ""
    if last_updated:
        try:
            updated_display = datetime.fromisoformat(
                last_updated.replace("Z", "+00:00")
            ).strftime("%B %d, %Y")
        except Exception:
            updated_display = last_updated[:10]

    # ── filter buttons ────────────────────────────────────────────────────────
    filter_html = '<button class="f-btn active" onclick="filterCat(\'all\',this)">All</button>\n'
    for cat in all_cats:
        color = CAT_COLOR.get(cat, DEFAULT_COLOR)
        sc = cat.replace("'", "\\'")
        filter_html += f'<button class="f-btn" onclick="filterCat(\'{sc}\',this)" style="--cc:{color}">{cat}</button>\n'

    # ── top stories section ───────────────────────────────────────────────────
    if featured:
        top_cards = "\n".join(card_html(p, featured=True) for p in featured)
        top_section = f"""
<section class="top-stories">
  <div class="section-label">⭐ Top Stories Today</div>
  <div class="top-grid">{top_cards}</div>
</section>"""
    else:
        top_section = ""

    # ── regular cards ─────────────────────────────────────────────────────────
    all_cards = "\n".join(card_html(p) for p in regular)

    total = len([p for p in posts if not p.get("skip")])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Claude AI · Marketing & Sales Insights</title>
<style>
:root{{
  --bg:#0f0f11; --surf:#1a1a1f; --surf2:#222228; --border:#2e2e38;
  --txt:#e8e8f0; --txt2:#9999b0; --acc:#7c5cfc;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:100vh}}

/* header */
header{{background:var(--surf);border-bottom:1px solid var(--border);padding:20px 32px}}
.hdr{{max-width:1200px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}}
.logo{{font-size:20px;font-weight:700}}.logo span{{color:var(--acc)}}
.meta{{font-size:12px;color:var(--txt2)}}

/* layout */
.container{{max-width:1200px;margin:0 auto;padding:28px 32px}}

/* stats */
.stats{{display:flex;gap:16px;margin-bottom:28px;flex-wrap:wrap}}
.stat{{background:var(--surf);border:1px solid var(--border);border-radius:10px;padding:14px 20px;min-width:120px}}
.stat-n{{font-size:26px;font-weight:700;color:var(--acc)}}
.stat-l{{font-size:11px;color:var(--txt2);margin-top:2px}}

/* top stories */
.top-stories{{background:linear-gradient(135deg,#1a1535,#111827);border:1px solid #3d2f7a;border-radius:14px;padding:24px;margin-bottom:32px}}
.section-label{{font-size:13px;font-weight:700;color:var(--acc);letter-spacing:.08em;text-transform:uppercase;margin-bottom:16px}}
.top-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}

/* filters */
.search-row{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:16px;align-items:center}}
.search-row input{{background:var(--surf);border:1px solid var(--border);color:var(--txt);padding:9px 14px;border-radius:8px;font-size:13px;outline:none;flex:1;min-width:200px;max-width:380px}}
.search-row input:focus{{border-color:var(--acc)}}
.filters{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px}}
.f-btn{{background:var(--surf2);border:1px solid var(--border);color:var(--txt2);padding:6px 14px;border-radius:20px;cursor:pointer;font-size:12px;transition:all .15s}}
.f-btn:hover{{color:var(--txt);border-color:var(--cc,var(--acc))}}
.f-btn.active{{background:var(--cc,var(--acc));color:#fff;border-color:var(--cc,var(--acc))}}

/* cards */
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:18px}}
.card{{background:var(--surf);border:1px solid var(--border);border-radius:12px;padding:18px;transition:border-color .15s,transform .15s}}
.card:hover{{border-color:var(--acc);transform:translateY(-2px)}}
.card.hidden{{display:none}}
.card--featured{{border-color:#3d2f7a;background:var(--surf2)}}
.card-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:6px}}
.badge{{font-size:11px;font-weight:600;color:#fff;padding:3px 10px;border-radius:12px;white-space:nowrap}}
.source{{font-size:11px;color:var(--txt2)}}
.card-title{{font-size:14px;font-weight:600;line-height:1.45;margin-bottom:8px}}
.card-title a{{color:var(--txt);text-decoration:none}}
.card-title a:hover{{color:var(--acc)}}
.insight{{background:#1b1b2e;border-left:3px solid var(--acc);padding:7px 11px;border-radius:0 6px 6px 0;font-size:12px;color:var(--txt);margin-bottom:8px;line-height:1.5}}
.summary{{font-size:12px;color:var(--txt2);line-height:1.6;margin-bottom:10px}}
.read-link{{font-size:12px;color:var(--acc);text-decoration:none;font-weight:600}}
.read-link:hover{{text-decoration:underline}}
.no-results{{text-align:center;color:var(--txt2);padding:50px 0;font-size:14px;display:none}}

footer{{text-align:center;padding:28px;color:var(--txt2);font-size:12px;border-top:1px solid var(--border);margin-top:32px}}

@media(max-width:640px){{.container{{padding:14px}}.grid,.top-grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>

<header>
  <div class="hdr">
    <div class="logo">Claude AI <span>Marketing & Sales</span> Insights</div>
    <div class="meta">Updated {updated_display} &nbsp;·&nbsp; Last 90 days only</div>
  </div>
</header>

<div class="container">

  <div class="stats">
    <div class="stat"><div class="stat-n">{total}</div><div class="stat-l">Curated Posts</div></div>
    <div class="stat"><div class="stat-n">{len(featured)}</div><div class="stat-l">Top Stories</div></div>
    <div class="stat"><div class="stat-n">{len(all_cats)}</div><div class="stat-l">Categories</div></div>
    <div class="stat"><div class="stat-n">Daily</div><div class="stat-l">Refresh</div></div>
  </div>

  {top_section}

  <div class="search-row">
    <input type="text" id="srch" placeholder="Search posts…" oninput="applyFilters()">
  </div>
  <div class="filters">
    {filter_html}
  </div>

  <div class="grid" id="grid">
    {all_cards}
  </div>
  <div class="no-results" id="noRes">No posts match this filter.</div>

</div>

<footer>
  Auto-curated daily from Reddit · Google News · Hacker News &nbsp;·&nbsp; Powered by Claude AI
  &nbsp;·&nbsp; <a href="https://github.com/gokulsk92/claude-tweets-reddits" style="color:var(--acc)">GitHub</a>
</footer>

<script>
let activeCat = 'all';
function filterCat(cat, btn) {{
  activeCat = cat;
  document.querySelectorAll('.f-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  applyFilters();
}}
function applyFilters() {{
  const q = document.getElementById('srch').value.toLowerCase();
  let vis = 0;
  document.querySelectorAll('#grid .card').forEach(c => {{
    const catOk = activeCat === 'all' || c.dataset.category === activeCat;
    const txtOk = !q || c.textContent.toLowerCase().includes(q);
    const show  = catOk && txtOk;
    c.classList.toggle('hidden', !show);
    if (show) vis++;
  }});
  document.getElementById('noRes').style.display = vis === 0 ? 'block' : 'none';
}}
</script>
</body>
</html>"""


def generate() -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    if not DATA_FILE.exists():
        with open(DOCS_DIR / "index.html", "w") as f:
            f.write(build_html([], ""))
        return
    with open(DATA_FILE) as f:
        data = json.load(f)
    posts = data.get("posts", [])
    last_updated = data.get("last_updated", "")
    html = build_html(posts, last_updated)
    with open(DOCS_DIR / "index.html", "w") as f:
        f.write(html)
    print(f"Dashboard: {len([p for p in posts if not p.get('skip')])} posts → docs/index.html")


if __name__ == "__main__":
    generate()
