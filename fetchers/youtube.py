from datetime import datetime
from utils import relative_to_dt, HSINCHU_KW, YOUTUBE_MAX_DAYS

# youtube-search-python uses httpx but passes a 'proxies' kwarg removed in httpx>=0.20.
# Patch the module-level httpx.post to silently drop that kwarg.
try:
    import httpx as _httpx
    _orig_httpx_post = _httpx.post
    def _patched_httpx_post(*args, **kwargs):
        kwargs.pop("proxies", None)
        return _orig_httpx_post(*args, **kwargs)
    _httpx.post = _patched_httpx_post
except Exception:
    pass


def fetch_youtube(query: str) -> list[dict]:
    try:
        from youtubesearchpython import VideosSearch
        search  = VideosSearch(query, limit=30)
        results = search.result().get("result", [])
        now     = datetime.now()
        articles = []
        for v in results:
            title = v.get("title", "")
            channel_name = v.get("channel", {}).get("name", "")

            if not any(kw.lower() in title.lower() for kw in HSINCHU_KW):
                continue

            pub_time = v.get("publishedTime", "")
            pub_dt   = relative_to_dt(pub_time) if pub_time else None

            if pub_dt and (now - pub_dt).days > YOUTUBE_MAX_DAYS:
                continue

            if pub_dt:
                pub_dt  = pub_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                pub_str = pub_dt.strftime("%Y-%m-%d")
            else:
                pub_str = pub_time

            thumbnails = v.get("thumbnails", [])
            image = thumbnails[0].get("url") if thumbnails else None

            snippet = ""
            if v.get("descriptionSnippet"):
                snippet = "".join(s.get("text", "") for s in v["descriptionSnippet"])

            articles.append({
                "title":     title,
                "link":      f"https://www.youtube.com/watch?v={v.get('id', '')}",
                "published": pub_str,
                "pub_dt":    pub_dt.isoformat() if pub_dt else "",
                "source":    f"YouTube · {channel_name or 'YouTube'}",
                "category":  "影片",
                "summary":   snippet[:200],
                "image":     image,
            })

            if len(articles) >= 12:
                break

        return articles
    except Exception as e:
        print(f"[YouTube error] {type(e).__name__}: {e}")
        return []
