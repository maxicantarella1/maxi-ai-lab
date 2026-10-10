
"""PostgreSQL connection and persistence models for Maxi AI Lab."""

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


DATABASE_URL = os.getenv("DATABASE_URL", "")

engine = (
    create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    if DATABASE_URL
    else None
)

SessionLocal = (
    sessionmaker(bind=engine, expire_on_commit=False)
    if engine is not None
    else None
)


class Base(DeclarativeBase):
    pass


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    prompt: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(100))
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    answer: Mapped[str | None] = mapped_column(Text)

    stages: Mapped[list["ExecutionStage"]] = relationship(
        back_populates="execution",
        cascade="all, delete-orphan",
    )


class ExecutionStage(Base):
    __tablename__ = "execution_stages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    execution_id: Mapped[str] = mapped_column(
        ForeignKey("executions.id"),
        index=True,
    )

    role: Mapped[str] = mapped_column(String(30))
    elapsed_ms: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    execution: Mapped["Execution"] = relationship(
        back_populates="stages",
    )


def init_db():
    """Create missing tables when the database is configured."""
    if engine is None:
        return

    Base.metadata.create_all(bind=engine)
