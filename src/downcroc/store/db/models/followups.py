from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class FollowUpDeclarationRow(Base):
    __tablename__ = "batch_followup_declarations"
    __table_args__ = (
        Index(
            "ux_followup_declarations_batch_step",
            "batch_id",
            "step_key",
            unique=True,
        ),
        Index("ix_followup_declarations_batch_state", "batch_id", "state"),
        Index("ix_followup_declarations_state_days", "state", "after_days"),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        Text, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    after_days: Mapped[int] = mapped_column(Integer, nullable=False)
    when: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    html: Mapped[str | None] = mapped_column(Text)
    require_approval: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    overrides_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    content_ref: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
