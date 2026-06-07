from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Filing(Base):
    __tablename__ = "filings"
    __table_args__ = (UniqueConstraint("ticker", "form_type", "period", name="uq_filing_ticker_form_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    form_type: Mapped[str] = mapped_column(String(20))
    period: Mapped[date]
    fiscal_year: Mapped[int]
    fiscal_quarter: Mapped[int]
    doc_name: Mapped[str] = mapped_column(String(255), unique=True)
    content_s3_key: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    page_indexes: Mapped[list["PageIndexRecord"]] = relationship(back_populates="filing", cascade="all, delete-orphan")


class PageIndexRecord(Base):
    __tablename__ = "page_indexes"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    filing_id: Mapped[Optional[int]] = mapped_column(ForeignKey("filings.id"), index=True)
    doc_name: Mapped[str] = mapped_column(String(255), index=True)
    doc_description: Mapped[Optional[str]] = mapped_column(Text)
    line_count: Mapped[Optional[int]]
    structure_s3_key: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    filing: Mapped[Optional["Filing"]] = relationship(back_populates="page_indexes")
