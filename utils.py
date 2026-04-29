import re
from datetime import datetime, timedelta, timezone

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
}

FOOD_KEYWORDS = ["美食", "餐廳", "小吃", "咖啡", "甜點", "燒烤", "火鍋", "拉麵", "壽司",
                 "牛肉麵", "早餐", "下午茶", "飲料", "滷肉飯", "便當", "麵包", "鍋物"]
ATTRACTION_KW = ["景點", "公園", "博物館", "老街", "步道", "海邊", "山區", "古蹟"]
ENTERTAINMENT_KW = ["演唱會", "音樂會", "展覽", "展出", "表演", "節慶", "嘉年華", "市集",
                    "夜市", "演出", "藝術節", "電影", "好玩", "推薦", "打卡", "週末活動"]
HSINCHU_KW = ["新竹", "竹科", "竹北", "竹東", "新豐", "新埔", "關西", "湖口", "hsinchu"]
YOUTUBE_MAX_DAYS = 14


def detect_category(title: str, hint_category: str) -> str:
    for kw in FOOD_KEYWORDS:
        if kw in title:
            return "美食"
    if hint_category != "新聞":
        return hint_category
    for kw in ATTRACTION_KW:
        if kw in title:
            return "景點"
    for kw in ENTERTAINMENT_KW:
        if kw in title:
            return "娛樂"
    return "新聞"


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_pub_date(entry) -> tuple[str, datetime | None]:
    try:
        dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        local_dt = dt.astimezone()
        return local_dt.strftime("%Y-%m-%d %H:%M"), local_dt.replace(tzinfo=None)
    except Exception:
        return entry.get("published") or "", None


def relative_to_dt(time_str: str) -> datetime | None:
    now = datetime.now()
    patterns = [
        (r"(\d+)\s*秒",    lambda n: timedelta(seconds=n)),
        (r"(\d+)\s*分鐘",  lambda n: timedelta(minutes=n)),
        (r"(\d+)\s*小時",  lambda n: timedelta(hours=n)),
        (r"(\d+)\s*天",    lambda n: timedelta(days=n)),
        (r"(\d+)\s*週",    lambda n: timedelta(weeks=n)),
        (r"(\d+)\s*個月",  lambda n: timedelta(days=n * 30)),
        (r"(\d+)\s+second", lambda n: timedelta(seconds=n)),
        (r"(\d+)\s+minute", lambda n: timedelta(minutes=n)),
        (r"(\d+)\s+hour",   lambda n: timedelta(hours=n)),
        (r"(\d+)\s+day",    lambda n: timedelta(days=n)),
        (r"(\d+)\s+week",   lambda n: timedelta(weeks=n)),
        (r"(\d+)\s+month",  lambda n: timedelta(days=n * 30)),
        (r"(\d+)\s+year",   lambda n: timedelta(days=n * 365)),
    ]
    for pattern, delta_fn in patterns:
        m = re.search(pattern, time_str, re.IGNORECASE)
        if m:
            return now - delta_fn(int(m.group(1)))
    return None


def roc_to_ad(roc_str: str) -> str | None:
    m = re.match(r"(\d{3})[-/](\d{1,2})[-/](\d{1,2})", roc_str.strip())
    if m:
        return f"{int(m.group(1)) + 1911}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
    return None
