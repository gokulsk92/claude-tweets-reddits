"""
Sends a daily HTML email digest of new Claude AI marketing/sales posts.
Uses Gmail SMTP with an App Password (set via GMAIL_USER + GMAIL_APP_PASSWORD env vars).
"""

import json
import os
import smtplib
import ssl
from datetime import datetime, timezone, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

DATA_FILE = Path(__file__).parent.parent / "data" / "posts.json"

RECIPIENT_EMAIL = "gokulsk@gmail.com"
DASHBOARD_URL = "https://gokulsk92.github.io/claude-tweets-reddits"

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


def get_recent_posts(hours: int = 25) -> list[dict]:
    """Return posts fetched in the last N hours."""
    if not DATA_FILE.exists():
        return []
    with open(DATA_FILE) as f:
        data = json.load(f)
    posts = data.get("posts", [])
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    recent = []
    for p in posts:
        fetched = p.get("fetched_at", "")
        if not fetched:
            continue
        try:
            dt = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
            if dt >= cutoff:
                recent.append(p)
        except ValueError:
            pass
    return recent


def build_email_html(posts: list[dict]) -> str:
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    if not posts:
        body = "<p style='color:#666;text-align:center;padding:40px 0;'>No new Claude AI marketing posts found today. Check back tomorrow!</p>"
    else:
        # Group by category
        by_cat: dict[str, list[dict]] = {}
        for p in posts:
            cat = p.get("category") or "General / Other"
            by_cat.setdefault(cat, []).append(p)

        body = ""
        for cat, cat_posts in sorted(by_cat.items()):
            color = CATEGORY_COLORS.get(cat, "#95a5a6")
            body += f"""
            <div style="margin-bottom:32px;">
              <h2 style="font-size:16px;font-weight:700;color:{color};border-bottom:2px solid {color};padding-bottom:8px;margin-bottom:16px;">
                {cat} ({len(cat_posts)})
              </h2>"""
            for p in cat_posts[:5]:  # Max 5 per category
                title = p.get("title", "Untitled")
                url = p.get("url", "#")
                insight = p.get("key_insight", "")
                source = p.get("source", "Unknown")
                summary = p.get("summary", "")[:200]
                body += f"""
              <div style="background:#f8f9fa;border-radius:8px;padding:16px;margin-bottom:12px;border-left:4px solid {color};">
                <p style="margin:0 0 6px;font-size:11px;color:#888;">{source}</p>
                <h3 style="margin:0 0 8px;font-size:15px;font-weight:600;">
                  <a href="{url}" style="color:#1a1a2e;text-decoration:none;">{title}</a>
                </h3>
                {"<p style='background:#fff;border-left:3px solid " + color + ";padding:8px 12px;margin:8px 0;font-size:13px;color:#333;border-radius:0 4px 4px 0;'>💡 " + insight + "</p>" if insight else ""}
                {"<p style='font-size:13px;color:#666;margin:6px 0 0;'>" + summary + "...</p>" if summary else ""}
                <a href="{url}" style="font-size:13px;color:{color};font-weight:600;text-decoration:none;">Read more →</a>
              </div>"""
            body += "</div>"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border-radius:12px;padding:28px;margin-bottom:24px;text-align:center;">
    <h1 style="color:white;font-size:22px;margin:0 0 6px;">Claude AI · Marketing & Sales</h1>
    <p style="color:#a0a0c0;font-size:14px;margin:0;">Daily Insight Digest · {today}</p>
    <p style="color:#7c5cfc;font-size:16px;font-weight:700;margin:12px 0 0;">{len(posts)} new posts today</p>
  </div>

  <!-- Posts -->
  <div style="background:white;border-radius:12px;padding:24px;margin-bottom:24px;">
    {body}
  </div>

  <!-- CTA -->
  <div style="text-align:center;margin-bottom:24px;">
    <a href="{DASHBOARD_URL}" style="background:#7c5cfc;color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;display:inline-block;">
      View Full Dashboard →
    </a>
  </div>

  <!-- Footer -->
  <p style="text-align:center;color:#999;font-size:12px;">
    Auto-curated from Reddit, Google News & Hacker News ·
    <a href="{DASHBOARD_URL}" style="color:#7c5cfc;">claude-tweets-reddits</a>
  </p>

</div>
</body>
</html>"""


def send_digest() -> None:
    sender_email = os.environ.get("GMAIL_USER")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not sender_email or not app_password:
        print("[warn] GMAIL_USER or GMAIL_APP_PASSWORD not set. Skipping email.")
        return

    posts = get_recent_posts(hours=25)
    print(f"Sending digest with {len(posts)} recent posts to {RECIPIENT_EMAIL}...")

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    subject = f"Claude AI Marketing Digest · {len(posts)} new posts · {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = RECIPIENT_EMAIL

    html_body = build_email_html(posts)
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, RECIPIENT_EMAIL, msg.as_string())
        print(f"Email sent successfully to {RECIPIENT_EMAIL}")
    except Exception as e:
        print(f"[error] Failed to send email: {e}")
        raise


if __name__ == "__main__":
    send_digest()
