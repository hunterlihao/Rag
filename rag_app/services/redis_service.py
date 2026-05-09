import json
import hashlib
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
    
    # ========== 优化1: RAG检索缓存 ==========
    def get_rag_retrieval(self, cache_key: str) -> list | None:
        """获取RAG检索缓存"""
        key = self._key("rag", "retrieval", cache_key)
        payload = self._run(self.client.get, key)
        if not payload:
            return None
        return json.loads(payload)
    
    def set_rag_retrieval(self, cache_key: str, documents: list, ttl: int = 300):
        """设置RAG检索缓存,默认5分钟"""
        key = self._key("rag", "retrieval", cache_key)
        self._run(
            self.client.setex,
            key,
            ttl,
            json.dumps(documents, ensure_ascii=False),
        )
    
    def delete_rag_retrieval(self, cache_key: str):
        """删除RAG检索缓存"""
        key = self._key("rag", "retrieval", cache_key)
        self._run(self.client.delete, key)
    
    # ========== 优化2: 向量检索结果缓存 ==========
    def get_vector_search(self, collection_name: str, query_text: str) -> list | None:
        """获取向量检索缓存"""
        # 安全优化: 使用SHA256替代MD5,防止哈希碰撞攻击
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()
        key = self._key("vector", "search", collection_name, query_hash)
        payload = self._run(self.client.get, key)
        if not payload:
            return None
        return json.loads(payload)
    
    def set_vector_search(self, collection_name: str, query_text: str, documents: list, ttl: int = None):
        """设置向量检索缓存,默认10分钟"""
        # 安全优化: 使用SHA256替代MD5
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()
        key = self._key("vector", "search", collection_name, query_hash)
        if ttl is None:
            ttl = config.REDIS_CACHE_TTL_VECTOR_SEARCH
        self._run(
            self.client.setex,
            key,
            ttl,
            json.dumps(documents, ensure_ascii=False),
        )
    
    def invalidate_vector_search(self, collection_name: str):
        """清理集合的所有向量检索缓存(上传新文档后调用)"""
        pattern = self._key("vector", "search", collection_name, "*")
        keys = self._run(self.client.keys, pattern)
        if keys:
            self._run(self.client.delete, *keys)
    
    # ========== 优化3: 模型实例状态缓存 ==========
    def get_model_status(self, model_id: str) -> dict | None:
        """获取模型加载状态"""
        key = self._key("model", "status", model_id)
        payload = self._run(self.client.get, key)
        if not payload:
            return None
        return json.loads(payload)
    
    def set_model_status(self, model_id: str, status: dict, ttl: int = None):
        """设置模型加载状态,默认1小时"""
        key = self._key("model", "status", model_id)
        if ttl is None:
            ttl = config.REDIS_CACHE_TTL_MODEL_STATUS
        self._run(
            self.client.setex,
            key,
            ttl,
            json.dumps(status, ensure_ascii=False),
        )
    
    # ========== 优化4: 用户偏好设置缓存 ==========
    def get_user_preferences(self, user_id: str) -> dict | None:
        """获取用户偏好设置"""
        key = self._key("user", "preferences", user_id)
        payload = self._run(self.client.get, key)
        if not payload:
            return None
        return json.loads(payload)
    
    def set_user_preferences(self, user_id: str, preferences: dict, ttl: int = None):
        """设置用户偏好设置,默认24小时"""
        key = self._key("user", "preferences", user_id)
        if ttl is None:
            ttl = config.REDIS_CACHE_TTL_USER_PREFERENCES
        self._run(
            self.client.setex,
            key,
            ttl,
            json.dumps(preferences, ensure_ascii=False),
        )
    
    def delete_user_preferences(self, user_id: str):
        """删除用户偏好缓存"""
        key = self._key("user", "preferences", user_id)
        self._run(self.client.delete, key)
    
    # ========== 优化5: 文档去重SHA256索引缓存 ==========
    def get_upload_sha256(self, user_id: str, content_sha256: str) -> dict | None:
        """获取上传文档SHA256去重缓存"""
        key = self._key("upload", "sha256", user_id, content_sha256)
        payload = self._run(self.client.get, key)
        if not payload:
            return None
        return json.loads(payload)
    
    def set_upload_sha256(self, user_id: str, content_sha256: str, doc_info: dict, ttl: int = None):
        """设置上传文档SHA256去重缓存,默认7天"""
        key = self._key("upload", "sha256", user_id, content_sha256)
        if ttl is None:
            ttl = config.REDIS_CACHE_TTL_UPLOAD_SHA256
        self._run(
            self.client.setex,
            key,
            ttl,
            json.dumps(doc_info, ensure_ascii=False),
        )
    
    # ========== 优化6: 知识库集合元信息缓存 ==========
    def get_collection_meta(self, user_id: str) -> dict | None:
        """获取知识库集合元信息"""
        key = self._key("collection", "meta", user_id)
        payload = self._run(self.client.get, key)
        if not payload:
            return None
        return json.loads(payload)
    
    def set_collection_meta(self, user_id: str, meta: dict, ttl: int = None):
        """设置知识库集合元信息,默认5分钟"""
        key = self._key("collection", "meta", user_id)
        if ttl is None:
            ttl = config.REDIS_CACHE_TTL_COLLECTION_META
        self._run(
            self.client.setex,
            key,
            ttl,
            json.dumps(meta, ensure_ascii=False),
        )
    
    def invalidate_collection_meta(self, user_id: str):
        """清理知识库元信息缓存(上传/删除文档后调用)"""
        key = self._key("collection", "meta", user_id)
        self._run(self.client.delete, key)
    
    def invalidate_upload_sha256_all(self, user_id: str):
        """清理用户所有上传SHA256缓存(删除所有文档后调用)"""
        pattern = self._key("upload", "sha256", user_id, "*")
        keys = self._run(self.client.keys, pattern)
        if keys:
            self._run(self.client.delete, *keys)
    
    # ========== 优化7: 问答意图分类缓存 ==========
    def get_query_intent(self, query_text: str) -> str | None:
        """获取查询意图分类"""
        # 安全优化: 使用SHA256替代MD5
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()
        key = self._key("intent", "query", query_hash)
        return self._run(self.client.get, key)
    
    def set_query_intent(self, query_text: str, intent: str, ttl: int = None):
        """设置查询意图分类,默认1小时"""
        # 安全优化: 使用SHA256替代MD5
        query_hash = hashlib.sha256(query_text.encode()).hexdigest()
        key = self._key("intent", "query", query_hash)
        if ttl is None:
            ttl = config.REDIS_CACHE_TTL_QUERY_INTENT
        self._run(self.client.setex, key, ttl, intent)
    
    # ========== 优化9: 用户会话消息热点缓存 ==========
    def get_session_messages(self, session_id: str) -> list | None:
        """获取会话消息热点缓存"""
        key = self._key("session", "messages", session_id, "recent")
        payload = self._run(self.client.get, key)
        if not payload:
            return None
        return json.loads(payload)
    
    def set_session_messages(self, session_id: str, messages: list, ttl: int = None):
        """设置会话消息热点缓存,默认30分钟"""
        key = self._key("session", "messages", session_id, "recent")
        if ttl is None:
            ttl = config.REDIS_CACHE_TTL_SESSION_MESSAGES
        self._run(
            self.client.setex,
            key,
            ttl,
            json.dumps(messages, ensure_ascii=False),
        )
    
    def invalidate_session_messages(self, session_id: str):
        """清理会话消息缓存(新消息后调用)"""
        key = self._key("session", "messages", session_id, "recent")
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
            raise RuntimeError(f"Redis 操作失败:{exc}") from exc
