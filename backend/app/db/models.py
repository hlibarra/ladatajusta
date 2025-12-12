from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ScrapedArticle(Base):
    __tablename__ = "scraped_articles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    source_name: Mapped[str] = mapped_column(String(80))
    source_url: Mapped[str] = mapped_column(String(2048), unique=True, index=True)

    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_text: Mapped[str] = mapped_column(Text)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())

    text_hash: Mapped[str] = mapped_column(String(64), index=True)

    publication: Mapped["Publication" | None] = relationship(back_populates="scraped_article", uselist=False)


class Publication(Base):
    __tablename__ = "publications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scraped_article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scraped_articles.id", ondelete="CASCADE"), unique=True
    )

    state: Mapped[str] = mapped_column(String(32), default="draft", index=True)  # draft|published|discarded

    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)

    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list)

    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scraped_article: Mapped[ScrapedArticle] = relationship(back_populates="publication")


class AIRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scraped_article_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scraped_articles.id"))
    publication_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("publications.id"), nullable=True)

    agent: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="ok")

    input_text: Mapped[str] = mapped_column(Text)
    output_text: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("publications.id", ondelete="CASCADE"), index=True)

    vote_type: Mapped[str] = mapped_column(String(16), index=True)  # hot|cold
    voter_key: Mapped[str] = mapped_column(String(128), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.utcnow())

    __table_args__ = (
        UniqueConstraint("publication_id", "voter_key", name="uq_vote_pub_voter"),
        Index("ix_votes_pub_type", "publication_id", "vote_type"),
    )
