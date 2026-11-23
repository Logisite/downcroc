from __future__ import annotations

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from downcroc.store.db.models.base import Base


class ExtensionKvRow(Base):
    __tablename__ = "extension_kv"

    extension_id: Mapped[str] = mapped_column(Text, primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class ExtensionApprovalRow(Base):
    __tablename__ = "extension_approvals"

    extension_id: Mapped[str] = mapped_column(Text, primary_key=True)
    manifest_digest: Mapped[str] = mapped_column(Text, nullable=False)
    capability_digest: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False, default="elevated")
    approved_at: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="cli")


class ExtensionStateRow(Base):
    __tablename__ = "extension_state"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[str] = mapped_column(Text, nullable=False, default="")
    enabled: Mapped[bool] = mapped_column(Integer, nullable=False, default=1)
    restarts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
