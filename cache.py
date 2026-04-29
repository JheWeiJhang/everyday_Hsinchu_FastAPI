import json
import time
from datetime import date, datetime
from pathlib import Path
from paths import data_path

CACHE_DIR = Path(data_path("cache"))
CACHE_DIR.mkdir(exist_ok=True)
CACHE_TTL = 1200  # 20 minutes (today only)

# In-memory layer: date_str -> (articles, saved_timestamp)
_mem: dict[str, tuple[list[dict], float]] = {}
# Dates currently being refreshed in the background
_refreshing: set[str] = set()


def cache_path(target_date: str) -> Path:
    return CACHE_DIR / f"{target_date}.json"


def _is_today(target_date: str) -> bool:
    return target_date == date.today().strftime("%Y-%m-%d")


def load_cache(target_date: str) -> list[dict] | None:
    """Return data only if fresh (TTL not expired). None otherwise."""
    # Memory first
    if target_date in _mem:
        data, ts = _mem[target_date]
        if not _is_today(target_date) or time.time() - ts < CACHE_TTL:
            return data

    # Fall back to disk
    p = cache_path(target_date)
    if not p.exists():
        return None
    if _is_today(target_date):
        if datetime.now().timestamp() - p.stat().st_mtime > CACHE_TTL:
            return None
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    _mem[target_date] = (data, p.stat().st_mtime)
    return data


def load_cache_stale(target_date: str) -> list[dict] | None:
    """Return data even if TTL has expired (for stale-while-revalidate)."""
    if target_date in _mem:
        return _mem[target_date][0]
    p = cache_path(target_date)
    if not p.exists():
        return None
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    _mem[target_date] = (data, p.stat().st_mtime)
    return data


def is_stale(target_date: str) -> bool:
    """True only when today's cache exists but the TTL has expired."""
    if not _is_today(target_date):
        return False
    if target_date in _mem:
        _, ts = _mem[target_date]
        return time.time() - ts > CACHE_TTL
    p = cache_path(target_date)
    if not p.exists():
        return False
    return datetime.now().timestamp() - p.stat().st_mtime > CACHE_TTL


def save_cache(target_date: str, data: list[dict]) -> None:
    _mem[target_date] = (data, time.time())
    with open(cache_path(target_date), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_refreshing(target_date: str) -> bool:
    return target_date in _refreshing


def mark_refreshing(target_date: str) -> None:
    _refreshing.add(target_date)


def unmark_refreshing(target_date: str) -> None:
    _refreshing.discard(target_date)
