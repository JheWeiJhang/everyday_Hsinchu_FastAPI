import re
import asyncio
import httpx
import feedparser
from datetime import datetime
from bs4 import BeautifulSoup
from utils import strip_html, parse_pub_date, detect_category, roc_to_ad, HEADERS

_GOV_CLIENT = dict(headers=HEADERS, timeout=10, verify=False, follow_redirects=True)


async def fetch_hsinchu_county_gov() -> list[dict]:
    try:
        async with httpx.AsyncClient(**_GOV_CLIENT) as client:
            r = await client.get("https://www.hsinchu.gov.tw/OpenData.aspx?SN=92F93E5891B49161")
        feed = await asyncio.to_thread(feedparser.parse, r.content)
        articles = []
        for entry in feed.entries[:20]:
            pub_str, pub_dt = parse_pub_date(entry)
            articles.append({
                "title":     strip_html(entry.get("title", "")),
                "link":      entry.get("link", ""),
                "published": pub_str,
                "pub_dt":    pub_dt.isoformat() if pub_dt else "",
                "source":    "新竹縣政府",
                "category":  detect_category(entry.get("title", ""), "新聞"),
                "summary":   strip_html(entry.get("summary", ""))[:200],
                "image":     None,
            })
        return articles
    except Exception as e:
        print(f"[County Gov error] {type(e).__name__}: {e}")
        return []


async def fetch_hsinchu_city_gov() -> list[dict]:
    try:
        async with httpx.AsyncClient(**_GOV_CLIENT) as client:
            r = await client.get("https://www.hccg.gov.tw/")
        soup = BeautifulSoup(r.text, "html.parser")
        articles, seen = [], set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "module=municipalnews" not in href and "module=isfocusnews" not in href:
                continue
            text = a.get_text(strip=True)
            if not text or text in seen:
                continue
            seen.add(text)

            roc_m = re.search(r"(\d{3}-\d{2}-\d{2})", text)
            if roc_m:
                ad_date = roc_to_ad(roc_m.group(1))
                title   = text.replace(roc_m.group(0), "").strip()
            else:
                ad_date, title = None, text

            if not title:
                continue

            pub_dt = None
            if ad_date:
                try:
                    pub_dt = datetime.strptime(ad_date, "%Y-%m-%d")
                except Exception:
                    pass

            full_link = ("https://www.hccg.gov.tw" + href) if href.startswith("/") else href
            articles.append({
                "title":     title[:120],
                "link":      full_link,
                "published": ad_date or "",
                "pub_dt":    pub_dt.isoformat() if pub_dt else "",
                "source":    "新竹市政府",
                "category":  detect_category(title, "新聞"),
                "summary":   "",
                "image":     None,
            })
        return articles[:25]
    except Exception as e:
        print(f"[City Gov error] {type(e).__name__}: {e}")
        return []


async def fetch_hsinchu_culture() -> list[dict]:
    _date_re  = re.compile(r"發布日期：(\d{4}-\d{2}-\d{2})")
    _loc_re   = re.compile(r"活動地點：([^\s|]{2,30})")
    _range_re = re.compile(r"\d{4}/\d{2}/\d{2}\s*[~～]\s*\d{4}/\d{2}/\d{2}")
    urls = [
        "https://www.hchcc.gov.tw/Tw/News/ActList?filter=e2ce565c-7042-466e-9b77-bb81937b8cf9",
        "https://www.hchcc.gov.tw/Tw/News/ActList?filter=fff0eeb8-d017-46fa-a3b8-547a4049499f",
    ]
    articles, seen = [], set()
    try:
        async with httpx.AsyncClient(**_GOV_CLIENT) as client:
            responses = await asyncio.gather(
                *[client.get(u) for u in urls], return_exceptions=True
            )
        for r in responses:
            if isinstance(r, Exception):
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for a_tag in soup.select('a[href*="ActDetail"]'):
                href = a_tag.get("href", "")
                text = a_tag.get_text(" ", strip=True)

                date_m = _date_re.search(text)
                if not date_m:
                    continue
                pub_date = date_m.group(1)

                before_meta = text.split(" | 發布日期：")[0]
                title = _range_re.sub("", before_meta).strip()
                if not title or len(title) < 3 or title in seen:
                    continue
                title = title[:80]
                seen.add(title)

                try:
                    pub_dt = datetime.strptime(pub_date, "%Y-%m-%d")
                except Exception:
                    pub_dt = None

                loc_m   = _loc_re.search(text)
                summary = f"活動地點：{loc_m.group(1)}" if loc_m else ""
                full_link = ("https://www.hchcc.gov.tw" + href) if href.startswith("/") else href

                articles.append({
                    "title":     title,
                    "link":      full_link,
                    "published": pub_date,
                    "pub_dt":    pub_dt.isoformat() if pub_dt else "",
                    "source":    "新竹縣文化局",
                    "category":  "娛樂",
                    "summary":   summary,
                    "image":     None,
                })
        return articles[:20]
    except Exception as e:
        print(f"[Culture Bureau error] {type(e).__name__}: {e}")
        return []
