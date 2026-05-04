import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_app import config
from rag_app.storage.models import User
from rag_app.utils.time_utils import to_utc_isoformat


class AuthService:
    def __init__(self, redis_service=None):
        self.redis_service = redis_service

    def hash_password(self, password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )

    def create_access_token(self, user: User) -> str:
        issued_at = datetime.now(timezone.utc)
        expire_at = issued_at + timedelta(
            minutes=config.API_ACCESS_TOKEN_EXPIRE_MINUTES
        )
        payload = {
            "sub": user.id,
            "jti": str(uuid.uuid4()),
            "token_version": int(user.token_version or 0),
            "iss": config.API_JWT_ISSUER,
            "aud": config.API_JWT_AUDIENCE,
            "iat": issued_at,
            "nbf": issued_at,
            "exp": expire_at,
        }
        return jwt.encode(payload, config.API_SECRET_KEY, algorithm=config.API_JWT_ALGORITHM)

    def decode_access_token(self, token: str) -> dict:
        return jwt.decode(
            token,
            config.API_SECRET_KEY,
            algorithms=[config.API_JWT_ALGORITHM],
            audience=config.API_JWT_AUDIENCE,
            issuer=config.API_JWT_ISSUER,
        )

    def is_token_revoked(self, payload: dict) -> bool:
        if self.redis_service is None:
            return False

        token_jti = str(payload.get("jti", "")).strip()
        return self.redis_service.is_token_revoked(token_jti)

    @staticmethod
    def is_token_current(payload: dict, user: User) -> bool:
        try:
            token_version = int(payload["token_version"])
        except (KeyError, TypeError, ValueError):
            return False
        return token_version == int(user.token_version or 0)

    def revoke_access_token(self, payload: dict):
        if self.redis_service is None:
            return

        token_jti = str(payload.get("jti", "")).strip()
        expires_at = payload.get("exp")
        if not token_jti or expires_at is None:
            return
        self.redis_service.revoke_token(token_jti, expires_at)

    def login_rate_limit_status(self, client_host: str, email: str) -> tuple[bool, int]:
        if self.redis_service is None:
            return True, 0

        current_count, ttl_seconds = self.redis_service.get_login_failures(
            self.build_login_bucket(client_host, email)
        )
        return current_count < config.LOGIN_RATE_LIMIT_MAX_ATTEMPTS, ttl_seconds

    def record_login_failure(self, client_host: str, email: str) -> tuple[int, int]:
        if self.redis_service is None:
            return 0, 0

        return self.redis_service.record_login_failure(
            self.build_login_bucket(client_host, email)
        )

    def clear_login_failures(self, client_host: str, email: str):
        if self.redis_service is None:
            return

        self.redis_service.clear_login_failures(
            self.build_login_bucket(client_host, email)
        )

    def register_rate_limit_status(self, client_host: str) -> tuple[bool, int]:
        if self.redis_service is None:
            return True, 0

        current_count, ttl_seconds = self.redis_service.get_register_attempts(
            self.build_register_bucket(client_host)
        )
        return current_count < config.REGISTER_RATE_LIMIT_MAX_ATTEMPTS, ttl_seconds

    def record_register_attempt(self, client_host: str) -> tuple[int, int]:
        if self.redis_service is None:
            return 0, 0

        return self.redis_service.record_register_attempt(
            self.build_register_bucket(client_host)
        )

    @staticmethod
    def build_login_bucket(client_host: str, email: str) -> str:
        normalized_host = (client_host or "unknown").strip() or "unknown"
        normalized_email = email.strip().lower()
        email_digest = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()[:24]
        return f"{normalized_host}:{email_digest}"

    @staticmethod
    def build_register_bucket(client_host: str) -> str:
        normalized_host = (client_host or "unknown").strip() or "unknown"
        return normalized_host

    @staticmethod
    def resolve_client_host(request) -> str:
        client = getattr(request, "client", None)
        direct_host = ""
        if client and getattr(client, "host", None):
            direct_host = str(client.host).strip()

        if not config.TRUST_PROXY_HEADERS:
            return direct_host or "unknown"

        if direct_host not in config.TRUSTED_PROXY_IPS:
            return direct_host or "unknown"

        forwarded_for = str(request.headers.get("x-forwarded-for", "")).strip()
        if forwarded_for:
            forwarded_host = forwarded_for.split(",")[0].strip()
            if forwarded_host:
                return forwarded_host

        real_ip = str(request.headers.get("x-real-ip", "")).strip()
        if real_ip:
            return real_ip

        return direct_host or "unknown"

    def find_user_by_email(self, database: Session, email: str) -> User | None:
        normalized_email = email.strip().lower()
        statement = select(User).where(User.email == normalized_email)
        return database.scalar(statement)

    def get_user(self, database: Session, user_id: str) -> User | None:
        statement = select(User).where(User.id == user_id)
        return database.scalar(statement)

    def register_user(self, database: Session, name: str, email: str, password: str) -> User:
        normalized_name = name.strip()
        normalized_email = email.strip().lower()

        if not normalized_name:
            raise ValueError("昵称不能为空。")
        if not normalized_email:
            raise ValueError("邮箱不能为空。")
        if len(password) < 6:
            raise ValueError("密码至少需要 6 位。")
        if self.find_user_by_email(database, normalized_email):
            raise ValueError("该邮箱已经注册过了。")

        user = User(
            id=str(uuid.uuid4()),
            name=normalized_name,
            email=normalized_email,
            password_hash=self.hash_password(password),
            is_admin=False,
        )
        database.add(user)
        database.commit()
        database.refresh(user)
        return user

    def authenticate_user(self, database: Session, email: str, password: str) -> User:
        user = self.find_user_by_email(database, email)
        if user is None or not self.verify_password(password, user.password_hash):
            raise ValueError("邮箱或密码不正确。")
        return user

    @staticmethod
    def serialize_user(user: User) -> dict:
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "is_admin": bool(user.is_admin),
            "created_at": to_utc_isoformat(user.created_at),
        }

    def ensure_admin_account(self, database: Session):
        admin_user = self.find_user_by_email(database, config.ADMIN_BOOTSTRAP_EMAIL)
        if admin_user is None:
            admin_user = User(
                id=str(uuid.uuid4()),
                name=config.ADMIN_BOOTSTRAP_NAME,
                email=config.ADMIN_BOOTSTRAP_EMAIL,
                password_hash=self.hash_password(config.ADMIN_BOOTSTRAP_PASSWORD),
                is_admin=True,
                token_version=0,
            )
            database.add(admin_user)
            database.commit()
            return

        if not admin_user.is_admin:
            admin_user.is_admin = True
            admin_user.token_version = int(admin_user.token_version or 0) + 1
            database.add(admin_user)
            database.commit()
