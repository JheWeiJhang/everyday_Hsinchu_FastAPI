from datetime import date as _date
from fastapi import APIRouter, BackgroundTasks, Query
import lifecycle
import cache as _cache
from cache import load_cache, load_cache_stale, save_cache
from models import NewsResponse, PingResponse
from fetchers.aggregator import all_articles_for_date

router = APIRouter(prefix="/api")


async def _background_refresh(target_date: str) -> None:
    """Fetch fresh data and update cache without blocking the response."""
    _cache.mark_refreshing(target_date)
    try:
        articles = await all_articles_for_date(target_date)
        save_cache(target_date, articles)
    except Exception as e:
        print(f"[background refresh error] {target_date}: {e}")
    finally:
        _cache.unmark_refreshing(target_date)


@router.get("/ping")
@router.post("/ping")
async def api_ping() -> PingResponse:
    lifecycle.update_heartbeat()
    return PingResponse(status="ok")


@router.get("/news", response_model=NewsResponse)
async def api_news(
    background_tasks: BackgroundTasks,
    date: str = Query(default=None),
    category: str = Query(default="all"),
    force: str = Query(default="0"),
):
    target_date  = date or _date.today().strftime("%Y-%m-%d")
    force_refresh = force == "1"

    from_cache = False

    if not force_refresh:
        fresh = load_cache(target_date)
        if fresh is not None:
            # Cache is fresh — return immediately
            articles, from_cache = fresh, True
        else:
            stale = load_cache_stale(target_date)
            if stale is not None and not _cache.is_refreshing(target_date):
                # Stale data exists — return it now, refresh quietly in background
                background_tasks.add_task(_background_refresh, target_date)
                articles, from_cache = stale, True
            else:
                # No cache at all (first run) — must wait
                articles = await all_articles_for_date(target_date)
                save_cache(target_date, articles)
    else:
        articles = await all_articles_for_date(target_date)
        save_cache(target_date, articles)

    if category != "all":
        articles = [a for a in articles if a["category"] == category]

    return NewsResponse(
        date=target_date,
        total=len(articles),
        from_cache=from_cache,
        articles=articles,
    )
