from typing import Optional
from pydantic import BaseModel


class Article(BaseModel):
    title: str
    link: str
    published: str
    source: str
    category: str
    summary: str
    image: Optional[str] = None


class NewsResponse(BaseModel):
    date: str
    total: int
    from_cache: bool
    articles: list[Article]


class PingResponse(BaseModel):
    status: str
