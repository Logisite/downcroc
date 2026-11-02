from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class RuntimeStateRow(Base):
    __tablename__ = "runtime_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_runtime_state_single"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    sending_paused_at: Mapped[str | None] = mapped_column(Text)
    sending_paused_until: Mapped[str | None] = mapped_column(Text)
    sending_paused_reason: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
