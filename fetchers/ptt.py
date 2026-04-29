import httpx
from datetime import date, datetime
from bs4 import BeautifulSoup
from utils import detect_category, HEADERS


async def fetch_ptt_board(board: str, hint_category: str) -> list[dict]:
    try:
        async with httpx.AsyncClient(
            headers={**HEADERS, "Cookie": "over18=1"}, timeout=8, follow_redirects=True
        ) as client:
            resp = await client.get(f"https://www.ptt.cc/bbs/{board}/index.html")
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        for item in soup.select("div.r-ent"):
            title_el = item.select_one("div.title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link  = "https://www.ptt.cc" + title_el["href"]
            date_el = item.select_one("div.date")
            pub_str = date_el.get_text(strip=True) if date_el else ""
            try:
                month, day = pub_str.strip().split("/")
                today  = date.today()
                pub_dt = datetime(today.year, int(month), int(day))
                pub_str = pub_dt.strftime("%Y-%m-%d")
            except Exception:
                pub_dt = None
            articles.append({
                "title":     title,
                "link":      link,
                "published": pub_str,
                "pub_dt":    pub_dt.isoformat() if pub_dt else "",
                "source":    f"PTT {board}板",
                "category":  detect_category(title, hint_category),
                "summary":   "",
                "image":     None,
            })
        return articles
    except Exception as e:
        print(f"[PTT/{board} error] {e}")
        return []
