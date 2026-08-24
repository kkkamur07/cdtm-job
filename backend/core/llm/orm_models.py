"""The one table ``core`` owns (``ask_quota``).

Core has no domain language and, on principle, no tables. This is the exception, and it is
an operational one rather than a domain one: the Ask rate limit is a spend ceiling on a
shared provider account, so it has to be counted somewhere every API instance can see. It
belongs to no board because a member who spends their allowance on the job board must not
get a fresh one on the directory. ``docs/ask.md`` records the exception.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.db import Base


class AskQuotaRow(Base):
    """One row per caller, rewritten in place once a minute.

    Not a log: the row for a caller is overwritten as each minute starts, so the table
    holds at most one row per member who has ever asked anything.
    """

    __tablename__ = "ask_quota"

    member_key: Mapped[str] = mapped_column(Text, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    asked: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (CheckConstraint("asked >= 0", name="asked_non_negative"),)
