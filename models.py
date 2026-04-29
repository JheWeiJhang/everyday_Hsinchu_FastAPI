from typing import Optional
from pydantic import BaseModel, field_validator


class Article(BaseModel):
    title: str
    link: str
    published: str
    source: str
    category: str
    summary: str
    image: Optional[str] = None

    @field_validator("published", "title", "link", "source", "category", "summary", mode="before")
    @classmethod
    def coerce_none_to_str(cls, v: object) -> str:
        return v if v is not None else ""


class NewsResponse(BaseModel):
    date: str
    total: int
    from_cache: bool
    articles: list[Article]


class PingResponse(BaseModel):
    status: str
