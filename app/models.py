import uuid
from datetime import datetime
from sqlalchemy import String, Text, ForeignKey, DateTime, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from fastapi_users.db import SQLAlchemyBaseUserTableUUID

class Base(DeclarativeBase):
    pass
class User(SQLAlchemyBaseUserTableUUID, Base):
    __allow_unmapped__ = True
class Source(Base):
    __tablename__ = "sources"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(Text)
    keywords: Mapped[str] = mapped_column(Text, default="")
    last_hash: Mapped[str| None] = mapped_column(String(64))
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Item(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("source_id", "link"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(Text)
    link: Mapped[str] = mapped_column(Text)
    content: Mapped[str| None] = mapped_column(Text)
    found_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    