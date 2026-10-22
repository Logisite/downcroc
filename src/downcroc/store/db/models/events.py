from __future__ import annotations

from typing import ClassVar

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class EventRow(Base):
    __tablename__ = "events"
    __table_args__: ClassVar[dict[str, bool]] = {"sqlite_autoincrement": True}

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
