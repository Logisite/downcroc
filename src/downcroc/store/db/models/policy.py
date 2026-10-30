from __future__ import annotations

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class PolicyOverrideRow(Base):
    __tablename__ = "policy_overrides"

    scope: Mapped[str] = mapped_column(Text, primary_key=True)
    daily_allowance: Mapped[int | None] = mapped_column(Integer)
    window_start: Mapped[int | None] = mapped_column(Integer)
    window_end: Mapped[int | None] = mapped_column(Integer)
    jitter_min: Mapped[int | None] = mapped_column(Integer)
    jitter_max: Mapped[int | None] = mapped_column(Integer)
    max_in_flight: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool | None] = mapped_column(Boolean)
    expires_at: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
