from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rag_app.storage.database import Base


class User(Base):
    __tablename__ = "rag_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")
    uploads: Mapped[list["UploadedDocument"]] = relationship(back_populates="uploader")
    upload_registries: Mapped[list["UploadedContentRegistry"]] = relationship(
        back_populates="uploader"
    )


class ChatSession(Base):
    __tablename__ = "rag_user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), default="新对话", nullable=False)
    message_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_message_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="sessions")


class UploadedDocument(Base):
    __tablename__ = "rag_uploaded_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    vector_doc_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="success", nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    uploader_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rag_users.id", ondelete="SET NULL"),
        nullable=True,
    )

    uploader: Mapped[User | None] = relationship(back_populates="uploads")


class UploadedContentRegistry(Base):
    __tablename__ = "rag_uploaded_content_registry"
    __table_args__ = (
        UniqueConstraint(
            "uploader_id",
            "content_sha256",
            name="uq_rag_uploaded_content_registry_user_sha256",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    uploader_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    vector_doc_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="processing", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    uploader: Mapped[User] = relationship(back_populates="upload_registries")
