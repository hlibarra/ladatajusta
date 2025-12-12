from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ScrapeRequest(BaseModel):
    source_name: str = Field(..., min_length=1, max_length=80)
    url: str = Field(..., min_length=10, max_length=2048)


class ScrapedArticleOut(BaseModel):
    id: uuid.UUID
    source_name: str
    source_url: str
    title: str | None
    extracted_text: str
    scraped_at: datetime


class PublicationOut(BaseModel):
    id: uuid.UUID
    state: str
    title: str
    summary: str
    body: str
    category: str | None
    tags: list[str]
    created_at: datetime
    published_at: datetime | None


class VoteRequest(BaseModel):
    vote_type: str = Field(..., pattern="^(hot|cold)$")


class VoteTotalsOut(BaseModel):
    publication_id: uuid.UUID
    hot: int
    cold: int
