import re
import asyncio
import httpx
from datetime import date, datetime, timedelta
from bs4 import BeautifulSoup
from utils import detect_category, HEADERS, HSINCHU_KW

# 每個看板各自有一個 Semaphore，允許三個看板同時查詢，但同一看板內部不並發
_board_sems: dict[str, asyncio.Semaphore] = {}

def _get_board_sem(board: str) -> asyncio.Semaphore:
    if board not in _board_sems:
        _board_sems[board] = asyncio.Semaphore(1)
    return _board_sems[board]

_MAX_PAGES_TODAY = 3    # 今天：最多往前翻幾頁
_REQ_DELAY       = 0.3  # 每次請求間隔（秒）


def _parse_articles(soup: BeautifulSoup, board: str, hint_category: str) -> list[dict]:
    articles = []
    for item in soup.select("div.r-ent"):
        title_el = item.select_one("div.title a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        link  = "https://www.ptt.cc" + title_el["href"]
        date_el = item.select_one("div.date")
        pub_dt  = _parse_ptt_date(date_el.get_text(strip=True) if date_el else "")
        articles.append({
            "title":     title,
            "link":      link,
            "published": pub_dt.strftime("%Y-%m-%d") if pub_dt else "",
            "pub_dt":    pub_dt.isoformat() if pub_dt else "",
            "source":    f"PTT {board}板",
            "category":  detect_category(title, hint_category),
            "summary":   "",
            "image":     None,
        })
    return articles


def _parse_ptt_date(pub_str: str) -> datetime | None:
    """
    將 PTT 列表頁的日期字串（如 '4/29'、' 4/ 6'）解析為 datetime。
    PTT 不顯示年份，規則：
    - 日期 <= 今天 → 直接用今年
    - 日期 > 今天  → 退一年（置底公告的未來日期也用此規則，
      但在 _page_date_range 裡用「30 天叢集」過濾掉）
    """
    try:
        parts = pub_str.strip().split("/")
        month, day = int(parts[0]), int(parts[1])
        today = date.today()
        dt = datetime(today.year, month, day)
        if dt.date() > today:
            dt = datetime(today.year - 1, month, day)
        return dt
    except Exception:
        return None


def _page_date_range(articles: list[dict]) -> tuple[date | None, date | None]:
    """
    回傳頁面上「真實文章」的最舊與最新日期。

    PTT 每頁有少量置底公告，其日期退一年後可能比真實文章新或舊幾個月，
    造成日期範圍失真。用「連續群聚」演算法：
    1. 把出現過的唯一日期排序
    2. 相鄰日期差 <= 7 天就歸同一群
    3. 取文章數最多的群，回傳該群的 (min, max)
    """
    from collections import defaultdict
    today = date.today()
    date_count: dict[date, int] = defaultdict(int)
    for a in articles:
        if a["pub_dt"]:
            try:
                d = datetime.fromisoformat(a["pub_dt"]).date()
                if d <= today:
                    date_count[d] += 1
            except Exception:
                pass
    if not date_count:
        return None, None

    sorted_dates = sorted(date_count)
    if len(sorted_dates) == 1:
        d = sorted_dates[0]
        return d, d

    # 建立連續群（相鄰日期差 <= 7 天為同群）
    clusters: list[list[date]] = [[sorted_dates[0]]]
    for d in sorted_dates[1:]:
        if (d - clusters[-1][-1]).days <= 7:
            clusters[-1].append(d)
        else:
            clusters.append([d])

    # 找文章最多的群
    best = max(clusters, key=lambda c: sum(date_count[d] for d in c))
    return min(best), max(best)


def _prev_page_url(soup: BeautifulSoup) -> str | None:
    for a in soup.select("div.btn-group-paging a"):
        if "上頁" in a.get_text():
            href = a.get("href", "")
            if href and "index" in href:
                return "https://www.ptt.cc" + href
    return None


def _get_max_page_num(soup: BeautifulSoup) -> int | None:
    """從「上頁」連結推算目前最大頁碼（上頁是 N-1，所以最大頁 = N）。"""
    for a in soup.select("div.btn-group-paging a"):
        if "上頁" in a.get_text():
            href = a.get("href", "")
            m = re.search(r"index(\d+)\.html", href)
            if m:
                return int(m.group(1)) + 1
    return None


async def fetch_ptt_board(
    board: str,
    hint_category: str,
    hsinchu_only: bool = False,
    target_date: str | None = None,
) -> list[dict]:
    """
    抓取 PTT 看板文章。
    - target_date=None 或今天 → 掃最新 3 頁（快）
    - target_date 為歷史日期  → Binary Search 定位目標頁（約 12 次翻頁）
    三個看板各自獨立 Semaphore，可同時查詢互不阻塞。
    """
    if target_date is None:
        target_date = date.today().strftime("%Y-%m-%d")

    sem = _get_board_sem(board)
    try:
        async with sem:
            return await _fetch_ptt_inner(board, hint_category, hsinchu_only, target_date)
    except httpx.HTTPStatusError as e:
        print(f"[PTT/{board} error] HTTP {e.response.status_code}: {e.request.url}")
        return []
    except httpx.TimeoutException:
        print(f"[PTT/{board} error] request timed out")
        return []
    except Exception as e:
        print(f"[PTT/{board} error] {type(e).__name__}: {e}")
        return []


async def _fetch_ptt_inner(
    board: str,
    hint_category: str,
    hsinchu_only: bool,
    target_date: str,
) -> list[dict]:
    target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
    today     = date.today()
    is_today  = target_dt == today

    async with httpx.AsyncClient(
        headers=HEADERS,
        cookies={"over18": "1"},
        timeout=10,
        follow_redirects=True,
    ) as client:

        async def fetch_page(page_id: int | str) -> tuple[BeautifulSoup, list[dict]]:
            """page_id: int（頁碼）或 str（完整 URL）"""
            await asyncio.sleep(_REQ_DELAY)
            url = (f"https://www.ptt.cc/bbs/{board}/index{page_id}.html"
                   if isinstance(page_id, int) else page_id)
            resp = await client.get(url)
            resp.raise_for_status()
            sp   = BeautifulSoup(resp.text, "html.parser")
            arts = _parse_articles(sp, board, hint_category)
            return sp, arts

        # ── 取得最新頁 ──────────────────────────────────────────────
        latest_url = f"https://www.ptt.cc/bbs/{board}/index.html"
        await asyncio.sleep(0.5)
        resp = await client.get(latest_url)
        resp.raise_for_status()
        latest_soup = BeautifulSoup(resp.text, "html.parser")

        # ── 今天：往前翻最多 3 頁 ──────────────────────────────────
        if is_today:
            all_articles: list[dict] = []
            soup = latest_soup
            for _ in range(_MAX_PAGES_TODAY):
                arts = _parse_articles(soup, board, hint_category)
                all_articles.extend(arts)
                if not any(a["pub_dt"].startswith(target_date) for a in arts if a["pub_dt"]):
                    break
                prev = _prev_page_url(soup)
                if not prev:
                    break
                soup, _ = await fetch_page(prev)
            return _finalize(all_articles, target_date, hsinchu_only)

        # ── 歷史日期：Binary Search ────────────────────────────────
        max_page = _get_max_page_num(latest_soup)
        if not max_page:
            print(f"[PTT/{board}] 無法取得最大頁碼")
            return []

        print(f"[PTT/{board}] 歷史查詢 {target_date}：max={max_page}，開始 Binary Search")

        lo, hi   = 1, max_page
        found_pg = None
        found_arts: list[dict] = []
        iters    = 0

        while lo <= hi:
            iters += 1
            mid = (lo + hi) // 2
            _, arts = await fetch_page(mid)
            oldest, newest = _page_date_range(arts)

            if oldest is None:
                # 整頁都是公告，沒有有效日期 → 往新方向
                lo = mid + 1
                continue

            if target_dt > newest:
                lo = mid + 1          # 目標比這頁更新
            elif target_dt < oldest:
                hi = mid - 1          # 目標比這頁更舊
            else:
                found_pg   = mid
                found_arts = arts
                print(f"[PTT/{board}] 找到目標頁 {found_pg}（Binary Search {iters} 次）")
                break

        if found_pg is None:
            print(f"[PTT/{board}] Binary Search 結束（{iters} 次）未找到 {target_date}")
            return []

        # ── 收集目標頁 ± 1 頁（避免同日文章跨頁）─────────────────
        all_articles = list(found_arts)
        for pg in (found_pg - 1, found_pg + 1):
            if 1 <= pg <= max_page:
                _, extra = await fetch_page(pg)
                all_articles.extend(extra)

        return _finalize(all_articles, target_date, hsinchu_only)


def _finalize(articles: list[dict], target_date: str, hsinchu_only: bool) -> list[dict]:
    if hsinchu_only:
        articles = [
            a for a in articles
            if any(kw.lower() in a["title"].lower() for kw in HSINCHU_KW)
        ]
    seen:   set[str]  = set()
    unique: list[dict] = []
    for a in articles:
        if a["link"] not in seen:
            seen.add(a["link"])
            unique.append(a)
    return unique
