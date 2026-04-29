import re
import asyncio
import feedparser
import httpx
from utils import strip_html, parse_pub_date, detect_category, HEADERS

RSS_SOURCES = [
    # ── 新竹 ──────────────────────────────────────────────────────────────────
    ("https://news.google.com/rss/search?q=%E6%96%B0%E7%AB%B9&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&when=7d",
     "新聞", "Google 新聞"),
    ("https://news.google.com/rss/search?q=%E6%96%B0%E7%AB%B9%E7%BE%8E%E9%A3%9F%E9%A4%90%E5%BB%B3&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&when=7d",
     "美食", "Google 新聞"),
    ("https://news.google.com/rss/search?q=%E6%96%B0%E7%AB%B9+%E6%99%AF%E9%BB%9E+%E6%97%85%E9%81%8A&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&when=7d",
     "景點", "Google 新聞"),
    ("https://news.google.com/rss/search?q=%E6%96%B0%E7%AB%B9+%E6%BC%94%E5%94%B1%E6%9C%83+%E5%B1%95%E8%A6%BD+%E6%B4%BB%E5%8B%95&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&when=7d",
     "娛樂", "Google 新聞"),
    # ── 竹北市（人口最多行政區，在地新聞豐富）────────────────────────────────
    ("https://news.google.com/rss/search?q=%E7%AB%B9%E5%8C%97%E5%B8%82&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&when=7d",
     "新聞", "Google 新聞・竹北"),
    # ── 竹科（科技園區動態）──────────────────────────────────────────────────
    ("https://news.google.com/rss/search?q=%E6%96%B0%E7%AB%B9+%E7%AB%B9%E7%A7%91&hl=zh-TW&gl=TW&ceid=TW:zh-Hant&when=7d",
     "新聞", "Google 新聞・竹科"),
    # ── 中央社地方新聞 ────────────────────────────────────────────────────────
    ("https://feeds.feedburner.com/rsscna/local",
     "新聞", "中央社"),
]


async def fetch_rss(url: str, hint_category: str, source_name: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=10, follow_redirects=True) as client:
            r = await client.get(url)
        # feedparser.parse() is CPU-only after content is fetched — safe to call sync
        feed = await asyncio.to_thread(feedparser.parse, r.content)
        articles = []
        for entry in feed.entries[:30]:
            title = strip_html(entry.get("title", ""))
            if not title:
                continue
            summary_raw = entry.get("summary", "")
            summary = strip_html(summary_raw)[:280]
            if source_name == "中央社" and "新竹" not in (title + summary):
                continue

            pub_str, pub_dt = parse_pub_date(entry)
            img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', summary_raw)

            articles.append({
                "title":     title,
                "link":      entry.get("link", ""),
                "published": pub_str,
                "pub_dt":    pub_dt.isoformat() if pub_dt else "",
                "source":    source_name,
                "category":  detect_category(title, hint_category),
                "summary":   summary,
                "image":     img_match.group(1) if img_match else None,
            })
        return articles
    except Exception as e:
        print(f"[RSS error] {source_name}: {type(e).__name__}: {e}")
        return []
