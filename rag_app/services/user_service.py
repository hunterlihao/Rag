from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from rag_app.services.auth_service import AuthService
from rag_app.services.knowledge_base import KnowledgeBaseService, cleanup_all_collection_locks
from rag_app.storage.chat_history import delete_session_messages
from rag_app.storage.models import ChatSession, UploadedContentRegistry, UploadedDocument, User


class UserService:
    def __init__(self, auth_service: AuthService):
        self.auth_service = auth_service

    def require_admin(self, user: User):
        if not user.is_admin:
            raise PermissionError("当前账号没有管理员权限。")

    def list_users(self, database: Session, keyword: str = "") -> list[User]:
        statement = select(User)
        normalized_keyword = keyword.strip().lower()
        if normalized_keyword:
            fuzzy_keyword = f"%{normalized_keyword}%"
            statement = statement.where(
                or_(
                    func.lower(User.name).like(fuzzy_keyword),
                    func.lower(User.email).like(fuzzy_keyword),
                )
            )
        statement = statement.order_by(desc(User.is_admin), desc(User.created_at))
        return database.scalars(statement).all()

    def get_user(self, database: Session, user_id: str) -> User | None:
        statement = select(User).where(User.id == user_id)
        return database.scalar(statement)

    def require_user(self, database: Session, user_id: str) -> User:
        user = self.get_user(database, user_id)
        if user is None:
            raise ValueError("目标用户不存在。")
        return user

    def create_user(
        self,
        database: Session,
        *,
        name: str,
        email: str,
        password: str,
        is_admin: bool = False,
    ) -> User:
        normalized_name = name.strip()
        normalized_email = email.strip().lower()

        if not normalized_name:
            raise ValueError("昵称不能为空。")
        if not normalized_email:
            raise ValueError("邮箱不能为空。")
        if len(password) < 6:
            raise ValueError("密码至少需要 6 位。")
        if self.auth_service.find_user_by_email(database, normalized_email):
            raise ValueError("该邮箱已经注册过了。")

        user = User(
            id=self._generate_user_id(),
            name=normalized_name,
            email=normalized_email,
            password_hash=self.auth_service.hash_password(password),
            is_admin=bool(is_admin),
        )
        database.add(user)
        database.commit()
        database.refresh(user)
        return user

    def update_profile(
        self,
        database: Session,
        user: User,
        *,
        name: str,
        email: str,
    ) -> User:
        normalized_name = name.strip()
        normalized_email = email.strip().lower()

        if not normalized_name:
            raise ValueError("昵称不能为空。")
        if not normalized_email:
            raise ValueError("邮箱不能为空。")

        existing_user = self.auth_service.find_user_by_email(database, normalized_email)
        if existing_user is not None and existing_user.id != user.id:
            raise ValueError("该邮箱已经被其他账号使用。")

        user.name = normalized_name
        user.email = normalized_email
        database.add(user)
        database.commit()
        database.refresh(user)
        return user

    def change_password(
        self,
        database: Session,
        user: User,
        *,
        current_password: str,
        new_password: str,
    ):
        if not self.auth_service.verify_password(current_password, user.password_hash):
            raise ValueError("当前密码不正确。")
        if len(new_password) < 6:
            raise ValueError("新密码至少需要 6 位。")

        user.password_hash = self.auth_service.hash_password(new_password)
        self.bump_token_version(user)
        database.add(user)
        database.commit()

    def admin_update_user(
        self,
        database: Session,
        actor: User,
        target_user: User,
        *,
        name: str,
        email: str,
        is_admin: bool,
        password: str = "",
    ) -> User:
        self.require_admin(actor)

        normalized_name = name.strip()
        normalized_email = email.strip().lower()
        desired_admin = bool(is_admin)

        if not normalized_name:
            raise ValueError("昵称不能为空。")
        if not normalized_email:
            raise ValueError("邮箱不能为空。")

        existing_user = self.auth_service.find_user_by_email(database, normalized_email)
        if existing_user is not None and existing_user.id != target_user.id:
            raise ValueError("该邮箱已经被其他账号使用。")

        if target_user.is_admin and not desired_admin and self.count_admin_users(database) <= 1:
            raise ValueError("系统至少需要保留一个管理员账号。")

        role_changed = bool(target_user.is_admin) != desired_admin
        target_user.name = normalized_name
        target_user.email = normalized_email
        target_user.is_admin = desired_admin

        normalized_password = password.strip()
        if normalized_password:
            if len(normalized_password) < 6:
                raise ValueError("新密码至少需要 6 位。")
            target_user.password_hash = self.auth_service.hash_password(normalized_password)

        if normalized_password or role_changed:
            self.bump_token_version(target_user)

        database.add(target_user)
        database.commit()
        database.refresh(target_user)
        return target_user

    def delete_user(self, database: Session, actor: User, user_id: str):
        self.require_admin(actor)
        target_user = self.require_user(database, user_id)

        if target_user.id == actor.id:
            raise ValueError("管理员不能删除当前登录账号。")
        if target_user.is_admin and self.count_admin_users(database) <= 1:
            raise ValueError("系统至少需要保留一个管理员账号。")

        self.cleanup_user_resources(database, target_user)
        database.delete(target_user)
        database.commit()

    def cleanup_user_resources(self, database: Session, user: User):
        sessions = database.scalars(
            select(ChatSession).where(ChatSession.user_id == user.id)
        ).all()
        for session in sessions:
            delete_session_messages(database, session.id)
            database.delete(session)

        uploads = database.scalars(
            select(UploadedDocument).where(UploadedDocument.uploader_id == user.id)
        ).all()
        for upload in uploads:
            database.delete(upload)

        registries = database.scalars(
            select(UploadedContentRegistry).where(UploadedContentRegistry.uploader_id == user.id)
        ).all()
        for registry in registries:
            database.delete(registry)

        # 清理向量库
        KnowledgeBaseService(user.id).delete_all_documents()
        
        # 清理该用户的集合锁,防止内存泄漏
        collection_name = KnowledgeBaseService(user.id).collection_name
        from rag_app.services.knowledge_base import release_collection_lock
        release_collection_lock(collection_name)

    def count_admin_users(self, database: Session) -> int:
        statement = select(func.count()).select_from(User).where(User.is_admin.is_(True))
        return int(database.scalar(statement) or 0)

    @staticmethod
    def bump_token_version(user: User):
        user.token_version = int(user.token_version or 0) + 1

    @staticmethod
    def _generate_user_id() -> str:
        import uuid

        return str(uuid.uuid4())
