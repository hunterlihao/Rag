import json
from datetime import datetime, timezone
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

from rag_app import config


class RedisService:
    def __init__(self):
        self.client = Redis.from_url(
            config.REDIS_URL,
            decode_responses=True,
        )

    def ping(self):
        self._run(self.client.ping)

    def get_login_failures(self, bucket: str) -> tuple[int, int]:
        return self.get_rate_limit_bucket("auth", "login", bucket)

    def record_login_failure(self, bucket: str) -> tuple[int, int]:
        return self.increment_rate_limit_bucket(
            "auth",
            "login",
            bucket,
            window_seconds=config.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
        )

    def clear_login_failures(self, bucket: str):
        self.clear_rate_limit_bucket("auth", "login", bucket)

    def get_register_attempts(self, bucket: str) -> tuple[int, int]:
        return self.get_rate_limit_bucket("auth", "register", bucket)

    def record_register_attempt(self, bucket: str) -> tuple[int, int]:
        return self.increment_rate_limit_bucket(
            "auth",
            "register",
            bucket,
            window_seconds=config.REGISTER_RATE_LIMIT_WINDOW_SECONDS,
        )

    def revoke_token(self, jti: str, expires_at: datetime | int | float | None):
        if not jti or expires_at is None:
            return

        if isinstance(expires_at, datetime):
            expiry_time = expires_at.astimezone(timezone.utc).timestamp()
        else:
            expiry_time = float(expires_at)

        ttl_seconds = max(1, int(expiry_time - datetime.now(timezone.utc).timestamp()))
        key = self._key("auth", "revoke", jti)
        self._run(self.client.setex, key, ttl_seconds, "1")

    def is_token_revoked(self, jti: str) -> bool:
        if not jti:
            return False
        key = self._key("auth", "revoke", jti)
        return bool(self._run(self.client.exists, key))

    def get_session_summaries(self, user_id: str) -> list[dict] | None:
        key = self._key("sessions", user_id)
        payload = self._run(self.client.get, key)
        if not payload:
            return None
        return json.loads(payload)

    def set_session_summaries(self, user_id: str, session_summaries: list[dict]):
        key = self._key("sessions", user_id)
        self._run(
            self.client.setex,
            key,
            config.SESSION_CACHE_TTL_SECONDS,
            json.dumps(session_summaries, ensure_ascii=False),
        )

    def clear_session_summaries(self, user_id: str):
        key = self._key("sessions", user_id)
        self._run(self.client.delete, key)

    def get_rate_limit_bucket(self, *parts: str) -> tuple[int, int]:
        key = self._key(*parts)
        count = self._run(self.client.get, key)
        ttl = self._run(self.client.ttl, key)
        return int(count or 0), max(int(ttl or 0), 0)

    def increment_rate_limit_bucket(self, *parts: str, window_seconds: int) -> tuple[int, int]:
        key = self._key(*parts)
        current_count = int(self._run(self.client.incr, key))
        if current_count == 1:
            self._run(self.client.expire, key, window_seconds)
            ttl = window_seconds
        else:
            ttl = max(int(self._run(self.client.ttl, key) or 0), 0)
        return current_count, ttl

    def clear_rate_limit_bucket(self, *parts: str):
        key = self._key(*parts)
        self._run(self.client.delete, key)

    def _key(self, *parts: str) -> str:
        normalized_parts = [config.REDIS_KEY_PREFIX]
        normalized_parts.extend(str(part).strip() for part in parts if str(part).strip())
        return ":".join(normalized_parts)

    @staticmethod
    def _run(operation, *args, **kwargs) -> Any:
        try:
            return operation(*args, **kwargs)
        except RedisError as exc:
            raise RuntimeError(f"Redis 操作失败：{exc}") from exc
