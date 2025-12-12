from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

from app.core.config import settings


@dataclass
class ProcessedContent:
    title: str
    summary: str
    body: str
    tags: list[str]
    category: str | None


_sentence_re = re.compile(r"(?<=[.!?])\s+")
_word_re = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]{4,}")


def _fallback_process(text: str, title_hint: str | None = None) -> ProcessedContent:
    clean = re.sub(r"\s+", " ", text).strip()
    sentences = _sentence_re.split(clean) if clean else []

    title = (title_hint or " ".join(clean.split()[:12]) or "Noticia").strip()
    if len(title) > 120:
        title = title[:117].rstrip() + "..."

    summary = " ".join(sentences[:2]).strip() if sentences else clean[:280]
    if len(summary) > 320:
        summary = summary[:317].rstrip() + "..."

    # body: bullets from first ~6 sentences
    bullet_src = sentences[:6] if sentences else [clean]
    bullets = []
    for s in bullet_src:
        s = s.strip()
        if not s:
            continue
        if len(s) > 220:
            s = s[:217].rstrip() + "..."
        bullets.append(f"- {s}")
    body = "\n".join(bullets) if bullets else clean

    # tags: top keywords
    words = [w.lower() for w in _word_re.findall(clean)]
    freq: dict[str, int] = {}
    for w in words:
        if w in {"para", "pero", "porque", "como", "donde", "cuando", "desde", "entre", "sobre", "tambien"}:
            continue
        freq[w] = freq.get(w, 0) + 1
    tags = [w for w, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:6]]

    return ProcessedContent(title=title, summary=summary, body=body, tags=tags, category=None)


async def _openai_process(text: str, title_hint: str | None = None) -> ProcessedContent:
    prompt = {
        "role": "user",
        "content": (
            "Sos un editor periodístico. Con el texto fuente, devolvé JSON con: "
            "title (<=120), summary (<=320, muy corto), body (bullets cortos), "
            "tags (lista de 3-8), category (opcional). "
            "NO plagies: reescribí en tus palabras.\n\n"
            f"TITLE_HINT: {title_hint or ''}\n\n"
            f"FUENTE:\n{text}"
        ),
    }

    headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"}
    payload = {
        "model": settings.openai_model,
        "messages": [prompt],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    content = data["choices"][0]["message"]["content"]
    obj = json.loads(content)

    title = str(obj.get("title") or (title_hint or "Noticia")).strip()
    summary = str(obj.get("summary") or "").strip()
    body = str(obj.get("body") or "").strip()
    tags = obj.get("tags") or []
    category = obj.get("category")

    if not isinstance(tags, list):
        tags = []

    return ProcessedContent(
        title=title[:120],
        summary=summary[:400],
        body=body,
        tags=[str(t).strip() for t in tags if str(t).strip()][:10],
        category=str(category).strip() if category else None,
    )


async def process_article(text: str, title_hint: str | None = None) -> ProcessedContent:
    if settings.openai_api_key:
        try:
            return await _openai_process(text, title_hint=title_hint)
        except Exception:
            # fallback
            return _fallback_process(text, title_hint=title_hint)
    return _fallback_process(text, title_hint=title_hint)
