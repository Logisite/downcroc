from __future__ import annotations

from sqlalchemy import Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class BatchRow(Base):
    __tablename__ = "batches"
    __table_args__ = (
        Index("ix_batches_state_created", "state", "created_at"),
        Index("ix_batches_campaign_key", "campaign_key"),
        Index("ix_batches_parent", "parent_batch_id"),
        Index(
            "ux_batches_source_submit_key",
            "source_hash",
            "submit_key",
            unique=True,
            sqlite_where=text("submit_key IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    parent_batch_id: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    source_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str | None] = mapped_column(Text)
    campaign_key: Mapped[str | None] = mapped_column(Text)
    submit_key: Mapped[str | None] = mapped_column(Text)
    producer_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    template_ref: Mapped[str | None] = mapped_column(Text)
    account_id: Mapped[str | None] = mapped_column(Text)
    routing_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    approval: Mapped[str] = mapped_column(Text, nullable=False, default="review")
    options_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    state: Mapped[str] = mapped_column(Text, nullable=False)
    sample_job_id: Mapped[str | None] = mapped_column(Text)
    samples_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ignored_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[str | None] = mapped_column(Text)
    paused_at: Mapped[str | None] = mapped_column(Text)
    paused_reason: Mapped[str | None] = mapped_column(Text)
