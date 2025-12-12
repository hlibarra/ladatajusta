from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime

import httpx
import trafilatura
from dateutil import parser as date_parser

from app.core.config import settings


@dataclass
class FetchedArticle:
    title: str | None
    raw_html: str
    extracted_text: str
    published_at: datetime | None
    text_hash: str


_whitespace_re = re.compile(r"\s+")


def _normalize_text(text: str) -> str:
    text = text.strip()
    text = _whitespace_re.sub(" ", text)
    return text


def _hash_text(text: str) -> str:
    normalized = _normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def fetch_and_extract(url: str) -> FetchedArticle:
    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        html = r.text

    downloaded = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        include_images=False,
        favor_precision=True,
        output_format="json",
    )
    if not downloaded:
        # fallback: try plain text extraction
        text = trafilatura.extract(html, output_format="txt") or ""
        extracted_text = _normalize_text(text)
        title = None
        published_at = None
    else:
        # `extract(..., output_format="json")` returns a JSON string
        try:
            data = json.loads(downloaded)
        except Exception:
            data = {}
        extracted_text = _normalize_text(str(data.get("text") or "").strip())
        title = (str(data.get("title")).strip() if data.get("title") else None)
        published_at = None
        if data.get("date"):
            try:
                published_at = date_parser.parse(str(data["date"]))
            except Exception:
                published_at = None

    if not extracted_text:
        extracted_text = _normalize_text(trafilatura.extract(html, output_format="txt") or "")

    text_hash = _hash_text(extracted_text)

    return FetchedArticle(
        title=title,
        raw_html=html,
        extracted_text=extracted_text,
        published_at=published_at,
        text_hash=text_hash,
    )
