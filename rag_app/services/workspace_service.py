import uuid
from datetime import datetime, timedelta

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from rag_app import config
from rag_app.services.knowledge_base import KnowledgeBaseService
from rag_app.storage.chat_history import delete_session_messages, load_session_messages
from rag_app.storage.models import ChatSession, UploadedContentRegistry, UploadedDocument, User
from rag_app.utils.time_utils import to_utc_isoformat

WELCOME_MESSAGE = "你好，我已经准备好结合知识库回答问题了。"
EMPTY_SESSION_PREVIEW = "还没有消息"


def truncate_text(text_value: str, max_length: int) -> str:
    compact_text = " ".join(text_value.split())
    if len(compact_text) <= max_length:
        return compact_text
    return compact_text[: max_length - 1] + "…"


class WorkspaceService:
    def __init__(self, redis_service=None):
        self.redis_service = redis_service

    def create_session(self, database: Session, user: User) -> ChatSession:
        session = ChatSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            title="新对话",
            message_count=0,
            last_message_preview=EMPTY_SESSION_PREVIEW,
        )
        database.add(session)
        database.commit()
        database.refresh(session)
        self.invalidate_session_cache(user.id)
        return session

    def get_session(self, database: Session, user: User, session_id: str) -> ChatSession | None:
        statement = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
        return database.scalar(statement)

    def require_session(self, database: Session, user: User, session_id: str) -> ChatSession:
        session = self.get_session(database, user, session_id)
        if session is None:
            raise ValueError("当前会话不存在，或者不属于当前账号。")
        return session

    def list_sessions(self, database: Session, user: User) -> list[dict]:
        cached_summaries = self.get_cached_session_summaries(user.id)
        if cached_summaries is not None:
            return cached_summaries

        statement = (
            select(ChatSession)
            .where(ChatSession.user_id == user.id)
            .order_by(desc(ChatSession.updated_at))
        )
        sessions = database.scalars(statement).all()
        self.ensure_session_summaries(database, sessions)
        session_summaries = [self.serialize_session_summary(session) for session in sessions]
        self.cache_session_summaries(user.id, session_summaries)
        return session_summaries

    def serialize_session_summary(self, session: ChatSession) -> dict:
        return {
            "id": session.id,
            "title": session.title,
            "preview": session.last_message_preview or EMPTY_SESSION_PREVIEW,
            "message_count": int(session.message_count or 0),
            "updated_at": to_utc_isoformat(session.updated_at),
            "created_at": to_utc_isoformat(session.created_at),
        }

    def get_session_detail(self, database: Session, user: User, session_id: str) -> dict:
        session = self.require_session(database, user, session_id)
        messages = load_session_messages(session.id)
        if self.ensure_session_summary(database, session, messages=messages):
            database.commit()
            database.refresh(session)
            self.invalidate_session_cache(user.id)
        return {
            **self.serialize_session_summary(session),
            "messages": messages,
            "welcome_message": WELCOME_MESSAGE,
        }

    def touch_session(
        self,
        database: Session,
        session: ChatSession,
        prompt: str,
        assistant_reply: str,
    ):
        if session.message_count is None or session.last_message_preview is None:
            existing_messages = load_session_messages(session.id)
            self.ensure_session_summary(database, session, messages=existing_messages)

        if session.title == "新对话" and prompt.strip():
            session.title = truncate_text(prompt, 18)
        session.message_count = int(session.message_count or 0) + 2
        session.last_message_preview = truncate_text(
            assistant_reply.strip() or prompt,
            34,
        )
        session.updated_at = datetime.utcnow()
        database.add(session)
        database.commit()
        database.refresh(session)
        self.invalidate_session_cache(session.user_id)

    def delete_session(self, database: Session, user: User, session_id: str) -> ChatSession:
        session = self.require_session(database, user, session_id)
        delete_session_messages(database, session.id)
        database.delete(session)
        database.commit()
        self.invalidate_session_cache(user.id)
        return session

    def list_uploads(self, database: Session, user: User) -> list[dict]:
        statement = (
            select(UploadedDocument)
            .options(selectinload(UploadedDocument.uploader))
            .where(UploadedDocument.uploader_id == user.id)
            .order_by(desc(UploadedDocument.created_at))
        )
        uploads = database.scalars(statement).all()
        return [self.serialize_upload(upload) for upload in uploads]

    def get_upload(self, database: Session, user: User, upload_id: str) -> UploadedDocument | None:
        statement = select(UploadedDocument).where(
            UploadedDocument.id == upload_id,
            UploadedDocument.uploader_id == user.id,
        )
        return database.scalar(statement)

    def require_upload(self, database: Session, user: User, upload_id: str) -> UploadedDocument:
        upload = self.get_upload(database, user, upload_id)
        if upload is None:
            raise ValueError("当前知识库文件不存在，或者不属于当前账号。")
        return upload

    def list_upload_entities(
        self,
        database: Session,
        user: User,
        upload_ids: list[str],
    ) -> list[UploadedDocument]:
        if not upload_ids:
            return []

        statement = select(UploadedDocument).where(
            UploadedDocument.uploader_id == user.id,
            UploadedDocument.id.in_(upload_ids),
        )
        return database.scalars(statement).all()

    def get_cached_session_summaries(self, user_id: str) -> list[dict] | None:
        if self.redis_service is None:
            return None
        return self.redis_service.get_session_summaries(user_id)

    def cache_session_summaries(self, user_id: str, session_summaries: list[dict]):
        if self.redis_service is None:
            return
        self.redis_service.set_session_summaries(user_id, session_summaries)

    def invalidate_session_cache(self, user_id: str):
        if self.redis_service is None:
            return
        self.redis_service.clear_session_summaries(user_id)
    
    # 优化4: 用户偏好设置缓存
    def get_user_preferences(self, user_id: str) -> dict | None:
        """获取用户偏好设置,优先Redis"""
        if self.redis_service is None:
            return None
        return self.redis_service.get_user_preferences(user_id)
    
    def save_user_preferences(self, user_id: str, preferences: dict):
        """保存用户偏好设置到Redis"""
        if self.redis_service is None:
            return
        self.redis_service.set_user_preferences(user_id, preferences)
    
    def delete_user_preferences(self, user_id: str):
        """删除用户偏好缓存"""
        if self.redis_service is None:
            return
        self.redis_service.delete_user_preferences(user_id)
    
    # 优化9: 会话消息热点缓存
    def get_cached_session_messages(self, session_id: str) -> list | None:
        """获取会话消息缓存"""
        if self.redis_service is None:
            return None
        return self.redis_service.get_session_messages(session_id)
    
    def cache_session_messages(self, session_id: str, messages: list):
        """缓存会话消息"""
        if self.redis_service is None:
            return
        self.redis_service.set_session_messages(session_id, messages)
    
    def invalidate_session_messages(self, session_id: str):
        """清理会话消息缓存"""
        if self.redis_service is None:
            return
        self.redis_service.invalidate_session_messages(session_id)

    def ensure_session_summaries(self, database: Session, sessions: list[ChatSession]):
        dirty_sessions = []
        for session in sessions:
            if self.ensure_session_summary(database, session):
                dirty_sessions.append(session)

        if dirty_sessions:
            database.commit()
            for session in dirty_sessions:
                database.refresh(session)

    def ensure_session_summary(
        self,
        database: Session,
        session: ChatSession,
        *,
        messages: list[dict] | None = None,
    ) -> bool:
        if session.message_count is not None and session.last_message_preview is not None:
            return False

        session_messages = messages if messages is not None else load_session_messages(session.id)
        preview = EMPTY_SESSION_PREVIEW
        if session_messages:
            preview = truncate_text(session_messages[-1]["content"], 34)

        title = session.title
        if title == "新对话":
            first_user_message = next(
                (
                    message["content"]
                    for message in session_messages
                    if message.get("role") == "user" and str(message.get("content", "")).strip()
                ),
                "",
            )
            if first_user_message:
                title = truncate_text(first_user_message, 18)

        session.title = title
        session.message_count = len(session_messages)
        session.last_message_preview = preview
        database.add(session)
        return True

    def reserve_upload_registry(
        self,
        database: Session,
        uploader: User,
        filename: str,
        content_type: str,
        size_bytes: int,
        content_sha256: str,
    ) -> UploadedContentRegistry | None:
        existing_upload = database.scalar(
            select(UploadedDocument).where(
                UploadedDocument.uploader_id == uploader.id,
                UploadedDocument.content_sha256 == content_sha256,
                UploadedDocument.status == "success",
            )
        )
        if existing_upload is not None:
            return None

        existing_registry = database.scalar(
            select(UploadedContentRegistry).where(
                UploadedContentRegistry.uploader_id == uploader.id,
                UploadedContentRegistry.content_sha256 == content_sha256,
            )
        )
        if existing_registry is not None:
            if self.is_upload_registry_stale(existing_registry):
                self.cleanup_stale_upload_registry(database, existing_registry)
            else:
                if existing_registry.status == "processing":
                    return None
                self.cleanup_stale_upload_registry(database, existing_registry)

        registry = UploadedContentRegistry(
            id=str(uuid.uuid4()),
            uploader_id=uploader.id,
            filename=filename,
            content_type=content_type or "unknown",
            size_bytes=size_bytes,
            content_sha256=content_sha256,
            status="processing",
        )
        database.add(registry)
        try:
            database.commit()
        except IntegrityError:
            database.rollback()
            return None

        database.refresh(registry)
        return registry

    def complete_upload(
        self,
        database: Session,
        registry_id: str,
        *,
        vector_doc_id: str | None,
        filename: str,
        content_type: str,
        size_bytes: int,
        content_sha256: str,
        status: str,
        message: str,
        uploader: User | None,
    ) -> UploadedDocument:
        registry = database.get(UploadedContentRegistry, registry_id)
        if registry is None:
            raise ValueError("上传登记不存在，无法完成知识库写入。")

        registry.filename = filename
        registry.content_type = content_type or "unknown"
        registry.size_bytes = size_bytes
        registry.content_sha256 = content_sha256
        registry.vector_doc_id = vector_doc_id
        registry.status = "ready" if vector_doc_id else "empty"
        registry.updated_at = datetime.utcnow()

        upload = UploadedDocument(
            id=str(uuid.uuid4()),
            filename=filename,
            content_type=content_type or "unknown",
            size_bytes=size_bytes,
            content_sha256=content_sha256,
            vector_doc_id=vector_doc_id,
            status=status,
            message=message,
            uploader_id=uploader.id if uploader else None,
        )

        database.add(registry)
        database.add(upload)
        try:
            database.commit()
        except Exception:
            database.rollback()
            raise

        database.refresh(upload)
        return upload

    def release_upload_registry(
        self,
        database: Session,
        registry_id: str | None = None,
        *,
        uploader_id: str | None = None,
        content_sha256: str | None = None,
    ):
        registry = None
        if registry_id:
            registry = database.get(UploadedContentRegistry, registry_id)
        elif uploader_id and content_sha256:
            registry = database.scalar(
                select(UploadedContentRegistry).where(
                    UploadedContentRegistry.uploader_id == uploader_id,
                    UploadedContentRegistry.content_sha256 == content_sha256,
                )
            )

        if registry is None:
            return

        database.delete(registry)
        database.commit()

    def cleanup_stale_upload_registries(self, database: Session) -> int:
        stale_before = datetime.utcnow() - timedelta(seconds=config.UPLOAD_REGISTRY_STALE_SECONDS)
        stale_registries = database.scalars(
            select(UploadedContentRegistry).where(
                UploadedContentRegistry.status == "processing",
                UploadedContentRegistry.updated_at <= stale_before,
            )
        ).all()

        if not stale_registries:
            return 0

        for registry in stale_registries:
            self.cleanup_stale_upload_registry(database, registry, commit=False)

        database.commit()
        return len(stale_registries)

    def cleanup_stale_upload_registry(
        self,
        database: Session,
        registry: UploadedContentRegistry,
        *,
        commit: bool = True,
    ):
        KnowledgeBaseService(registry.uploader_id).delete_documents_by_content_sha256(
            registry.content_sha256
        )
        database.delete(registry)
        if commit:
            database.commit()

    @staticmethod
    def is_upload_registry_stale(registry: UploadedContentRegistry) -> bool:
        if registry.status != "processing":
            return False

        stale_before = datetime.utcnow() - timedelta(seconds=config.UPLOAD_REGISTRY_STALE_SECONDS)
        return registry.updated_at <= stale_before

    def delete_upload(self, database: Session, upload: UploadedDocument):
        database.delete(upload)
        database.commit()

    def delete_upload_with_registry(self, database: Session, upload: UploadedDocument):
        registry = None
        if upload.uploader_id and upload.content_sha256:
            registry = database.scalar(
                select(UploadedContentRegistry).where(
                    UploadedContentRegistry.uploader_id == upload.uploader_id,
                    UploadedContentRegistry.content_sha256 == upload.content_sha256,
                )
            )

        database.delete(upload)
        if registry is not None:
            database.delete(registry)
        database.commit()

    def serialize_upload(self, upload: UploadedDocument) -> dict:
        return {
            "id": upload.id,
            "name": upload.filename,
            "type": upload.content_type,
            "size": upload.size_bytes,
            "status": upload.status,
            "message": upload.message,
            "duplicate": upload.status == "warning" and "已经处理过" in upload.message,
            "uploaded_at": to_utc_isoformat(upload.created_at),
            "uploader_name": upload.uploader.name if upload.uploader else "未知",
        }
