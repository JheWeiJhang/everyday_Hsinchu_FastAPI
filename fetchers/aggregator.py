import re
import asyncio
from datetime import date, datetime, timedelta

from fetchers.rss import fetch_rss, RSS_SOURCES
from fetchers.ptt import fetch_ptt_board
from fetchers.gov import fetch_hsinchu_county_gov, fetch_hsinchu_city_gov, fetch_hsinchu_culture
from fetchers.youtube import fetch_youtube
from utils import YOUTUBE_MAX_DAYS


async def all_articles_for_date(target_date: str) -> list[dict]:
    today_str = date.today().strftime("%Y-%m-%d")
    is_today  = target_date == today_str

    # Build RSS coroutines — inject date range for historical queries
    rss_coros = []
    for url, category, source in RSS_SOURCES:
        if source == "Google 新聞" and not is_today:
            dt      = datetime.strptime(target_date, "%Y-%m-%d")
            next_dt = dt + timedelta(days=1)
            base_q  = re.search(r"q=([^&]+)", url)
            if base_q:
                q   = base_q.group(1) + f"+after:{dt.strftime('%Y-%m-%d')}+before:{next_dt.strftime('%Y-%m-%d')}"
                url = re.sub(r"q=[^&]+", f"q={q}", url)
                url = url.replace("&when=7d", "")
        rss_coros.append(fetch_rss(url, category, source))

    # All sources fire at once
    # Food / travel 是全國性看板，加 hsinchu_only=True 只取含新竹關鍵字的文章
    raw_coros = rss_coros + [
        fetch_ptt_board("Hsinchu", "生活"),
        fetch_ptt_board("Food", "美食", hsinchu_only=True),
        fetch_ptt_board("travel", "景點", hsinchu_only=True),
        fetch_hsinchu_county_gov(),
        fetch_hsinchu_city_gov(),
        fetch_hsinchu_culture(),
    ]

    # YouTube is synchronous (youtube-search-python) — run in thread pool.
    # Cap at 25 s: the library sometimes hangs on network issues.
    # Fetch for today AND recent dates (within YOUTUBE_MAX_DAYS); date filtering
    # handles which videos actually appear on each historical date.
    target_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
    days_ago   = (date.today() - target_dt).days
    fetch_yt   = days_ago <= YOUTUBE_MAX_DAYS  # today=0, yesterday=1, …

    if fetch_yt:
        youtube_coro = asyncio.wait_for(
            asyncio.to_thread(fetch_youtube, "新竹"), timeout=25
        )
        all_coros = raw_coros + [youtube_coro]
    else:
        all_coros = raw_coros

    results = await asyncio.gather(*all_coros, return_exceptions=True)

    raw:      list[dict] = []
    flexible: list[dict] = []
    n_raw = len(raw_coros)

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"[fetcher error] task {i}: {result}")
            continue
        # YouTube is the last task when fetch_yt=True.
        # Today → flexible (skip strict date filter, pub_dt may be imprecise).
        # Recent non-today → raw (strict date filter matches pub_dt to target_date).
        if fetch_yt and i == n_raw:
            if is_today:
                flexible.extend(result)
            else:
                raw.extend(result)
        else:
            raw.extend(result)

    filtered: list[dict] = []
    for a in raw:
        if a["pub_dt"]:
            if a["pub_dt"][:10] != target_date:
                continue
        filtered.append(a)
    filtered.extend(flexible)

    if not filtered and is_today:
        filtered = raw

    seen:   set[str]  = set()
    unique: list[dict] = []
    for a in filtered:
        key = a["link"] or a["title"]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    unique.sort(key=lambda x: x["pub_dt"], reverse=True)

    for a in unique:
        a.pop("pub_dt", None)

    return unique
