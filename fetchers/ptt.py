import asyncio
import httpx
from datetime import date, datetime
from bs4 import BeautifulSoup
from utils import detect_category, HEADERS, HSINCHU_KW

# PTT blocks concurrent connections from the same client — serialize all board fetches
_ptt_sem = asyncio.Semaphore(1)

# 每次最多往前翻幾頁（含最新頁）
_MAX_PAGES = 3


def _parse_articles(soup: BeautifulSoup, board: str, hint_category: str) -> list[dict]:
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


def _prev_page_url(soup: BeautifulSoup) -> str | None:
    """從 PTT 頁面的分頁列取得「上頁」的完整 URL。"""
    for a in soup.select("div.btn-group-paging a"):
        if "上頁" in a.get_text():
            href = a.get("href", "")
            if href and "index" in href:
                return "https://www.ptt.cc" + href
    return None


async def fetch_ptt_board(
    board: str,
    hint_category: str,
    hsinchu_only: bool = False,
) -> list[dict]:
    """
    從最新頁開始，最多往前翻 _MAX_PAGES 頁，確保當日文章不會因翻頁而遺漏。
    hsinchu_only=True：只保留含新竹關鍵字的文章（全國性看板用）。
    """
    today_str = date.today().strftime("%Y-%m-%d")
    url = f"https://www.ptt.cc/bbs/{board}/index.html"

    try:
        async with _ptt_sem:
            await asyncio.sleep(0.8)  # brief pause so boards don't hammer PTT simultaneously
            return await _fetch_ptt_board_inner(board, hint_category, hsinchu_only, today_str, url)
    except httpx.HTTPStatusError as e:
        print(f"[PTT/{board} error] HTTP {e.response.status_code}: {e.request.url}")
        return []
    except httpx.TimeoutException:
        print(f"[PTT/{board} error] request timed out")
        return []
    except Exception as e:
        print(f"[PTT/{board} error] {type(e).__name__}: {e}")
        return []


async def _fetch_ptt_board_inner(
    board: str,
    hint_category: str,
    hsinchu_only: bool,
    today_str: str,
    url: str,
) -> list[dict]:
    all_articles: list[dict] = []
    async with httpx.AsyncClient(
        headers=HEADERS,
        cookies={"over18": "1"},
        timeout=10,
        follow_redirects=True,
    ) as client:
        for _ in range(_MAX_PAGES):
            resp = await client.get(url)
            resp.raise_for_status()

            if "r-list-container" not in resp.text:
                print(f"[PTT/{board}] unexpected page at {url}, stopping")
                break

            soup = BeautifulSoup(resp.text, "html.parser")
            page_articles = _parse_articles(soup, board, hint_category)
            all_articles.extend(page_articles)

            # 如果這頁已沒有今天的文章，就不需要再往前翻
            has_today = any(a["pub_dt"].startswith(today_str) for a in page_articles if a["pub_dt"])
            if not has_today:
                break

            prev = _prev_page_url(soup)
            if not prev:
                break
            url = prev

    # 全國性看板：只保留含新竹關鍵字的文章
    if hsinchu_only:
        all_articles = [
            a for a in all_articles
            if any(kw.lower() in a["title"].lower() for kw in HSINCHU_KW)
        ]

    return all_articles
