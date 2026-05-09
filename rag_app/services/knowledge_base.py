import os
import logging
from threading import Lock, RLock
import uuid
from datetime import datetime
from typing import BinaryIO

from langchain_chroma import Chroma

from rag_app import config
from rag_app.loaders.document_extractors import extract_text_from_file

logger = logging.getLogger(__name__)
DUPLICATE_MESSAGE = "文件已经处理过了"
_collection_lock_guard = Lock()
_collection_locks: dict[str, RLock] = {}
_collection_lock_refs: dict[str, int] = {}  # 引用计数


def get_collection_lock(collection_name: str) -> RLock:
    """获取集合锁,使用引用计数管理"""
    with _collection_lock_guard:
        lock = _collection_locks.get(collection_name)
        if lock is None:
            lock = RLock()
            _collection_locks[collection_name] = lock
            _collection_lock_refs[collection_name] = 0
        _collection_lock_refs[collection_name] = _collection_lock_refs.get(collection_name, 0) + 1
        return lock


def release_collection_lock(collection_name: str):
    """释放集合锁,当引用计数为0时删除锁对象"""
    with _collection_lock_guard:
        if collection_name in _collection_lock_refs:
            _collection_lock_refs[collection_name] -= 1
            if _collection_lock_refs[collection_name] <= 0:
                # 引用计数为0,删除锁对象
                _collection_locks.pop(collection_name, None)
                _collection_lock_refs.pop(collection_name, None)
                logger.debug("清理集合锁: %s", collection_name)


def cleanup_all_collection_locks():
    """清理所有集合锁(用于用户删除等场景)"""
    with _collection_lock_guard:
        count = len(_collection_locks)
        _collection_locks.clear()
        _collection_lock_refs.clear()
        if count > 0:
            logger.info("清理了 %d 个集合锁", count)


class KnowledgeBaseService(object):

    def __init__(self, user_id: str | None = None, redis_service=None):
        self.user_id = user_id
        self.redis_service = redis_service
        self.collection_name = config.build_user_collection_name(user_id)
        self.chroma = Chroma(
            **config.build_chroma_kwargs(
                collection_name=self.collection_name,
                embedding_function=config.OLLAMA_EMBEDDING_FUNCTION,
            )
        )
        self.spliter = config.TEXT_SPLITTER

    def upload_by_str(self, data: str, filename: str):
        lock = get_collection_lock(self.collection_name)
        try:
            with lock:
                return self._save_document_text(
                    text=data,
                    filename=filename,
                    content_sha256=None,
                )
        finally:
            release_collection_lock(self.collection_name)

    def upload_by_file(
        self,
        file_source: bytes | BinaryIO,
        filename: str,
        *,
        content_sha256: str | None = None,
    ):
        text = extract_text_from_file(file_source, filename)
        lock = get_collection_lock(self.collection_name)
        try:
            with lock:
                return self._save_document_text(
                    text=text,
                    filename=filename,
                    content_sha256=content_sha256,
                )
        finally:
            release_collection_lock(self.collection_name)

    def _save_document_text(
        self,
        text: str,
        filename: str,
        content_sha256: str | None,
    ):
        normalized_text = text.strip()
        if not normalized_text:
            return {
                "message": "未提取到可用文本，未写入知识库",
                "duplicate": False,
                "content_sha256": content_sha256,
                "document_id": None,
                "chunk_count": 0,
            }

        # 检查是否重复上传(优先检查Redis缓存)
        if content_sha256 and self.redis_service:
            try:
                cached = self.redis_service.get_upload_sha256(
                    str(self.user_id),
                    content_sha256
                )
                if cached and cached.get("duplicate"):
                    # 重复文件,直接返回缓存信息
                    return {
                        "message": f"文件已存在: {cached.get('filename', filename)} (共 {cached.get('chunk_count', 0)} 个片段)",
                        "duplicate": True,
                        "content_sha256": content_sha256,
                        "document_id": cached.get("doc_id"),
                        "chunk_count": cached.get("chunk_count", 0),
                    }
            except Exception:
                logger.debug("SHA256去重缓存检查失败")

        if len(normalized_text) > config.MAX_SPLIT_CHAR_NUM:
            knowledge_chunks: list[str] = self.spliter.split_text(normalized_text)
        else:
            knowledge_chunks = [normalized_text]

        if content_sha256:
            self.delete_documents_by_content_sha256(content_sha256)
            document_id = content_sha256
        else:
            document_id = str(uuid.uuid4())

        metadata = {
            "source": filename,
            "document_id": document_id,
            "content_sha256": content_sha256 or "",
            "source_type": os.path.splitext(filename)[1].lstrip(".").lower() or "txt",
            "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "operator": str(self.user_id or ""),
            "user_key": config.sanitize_user_key(self.user_id),
        }
        self.chroma.add_texts(
            knowledge_chunks,
            ids=[f"{document_id}:{index}" for index, _ in enumerate(knowledge_chunks, start=1)],
            metadatas=[metadata.copy() for _ in knowledge_chunks],
        )
        
        # 优化5: 写入SHA256去重缓存
        if self.redis_service and content_sha256:
            try:
                self.redis_service.set_upload_sha256(
                    str(self.user_id),
                    content_sha256,
                    {
                        "duplicate": True,
                        "doc_id": document_id,
                        "filename": filename,
                        "chunk_count": len(knowledge_chunks)
                    }
                )
            except Exception:
                logger.debug("SHA256去重缓存写入失败")
        
        # 优化6: 清理知识库元信息缓存
        if self.redis_service:
            try:
                self.redis_service.invalidate_collection_meta(str(self.user_id))
            except Exception:
                pass

        return {
            "message": f"上传成功，共写入 {len(knowledge_chunks)} 个文本片段",
            "duplicate": False,
            "content_sha256": content_sha256,
            "document_id": document_id,
            "chunk_count": len(knowledge_chunks),
        }

    def delete_documents_by_content_sha256(self, content_sha256: str | None) -> int:
        if not content_sha256:
            return 0

        lock = get_collection_lock(self.collection_name)
        try:
            with lock:
                result = self.chroma.get(where={"content_sha256": content_sha256})
                chunk_ids = [str(item) for item in result.get("ids", [])]

                if chunk_ids:
                    self.chroma.delete(ids=chunk_ids)
                return len(chunk_ids)
        finally:
            release_collection_lock(self.collection_name)

    def delete_all_documents(self) -> int:
        lock = get_collection_lock(self.collection_name)
        try:
            with lock:
                result = self.chroma.get()
                chunk_ids = [str(item) for item in result.get("ids", [])]
                if chunk_ids:
                    self.chroma.delete(ids=chunk_ids)
                
                # 优化6: 清理知识库元信息缓存
                if self.redis_service:
                    try:
                        self.redis_service.invalidate_collection_meta(str(self.user_id))
                        # 清理向量检索缓存
                        self.redis_service.invalidate_vector_search(self.collection_name)
                    except Exception:
                        pass
                
                return len(chunk_ids)
        finally:
            release_collection_lock(self.collection_name)

    def delete_document(
        self,
        document_id: str | None = None,
    ) -> dict:
        if not document_id:
            raise ValueError("旧知识库记录缺少向量文档标识，无法安全删除，请重新导入后再删除。")

        lock = get_collection_lock(self.collection_name)
        try:
            with lock:
                result = self.chroma.get(where={"document_id": document_id})
                chunk_ids = [str(item) for item in result.get("ids", [])]

                if chunk_ids:
                    self.chroma.delete(ids=chunk_ids)
            
            # 优化6: 清理知识库元信息缓存
            if self.redis_service:
                try:
                    self.redis_service.invalidate_collection_meta(str(self.user_id))
                except Exception:
                    pass

            return {
                "deleted_chunks": len(chunk_ids),
                "message": f"已删除 {len(chunk_ids)} 个知识片段",
            }
        finally:
            release_collection_lock(self.collection_name)
    
    # 优化6: 获取知识库元信息
    def get_collection_metadata(self) -> dict:
        """获取知识库元信息,优先使用Redis缓存"""
        # 尝试缓存
        if self.redis_service:
            try:
                cached = self.redis_service.get_collection_meta(str(self.user_id))
                if cached is not None:
                    return cached
            except Exception:
                pass
        
        # 查询实际数据
        lock = get_collection_lock(self.collection_name)
        try:
            with lock:
                result = self.chroma.get()
                chunk_ids = result.get("ids", [])
                
                # 统计文档数(去重)
                document_ids = set()
                for chunk_id in chunk_ids:
                    if ":" in chunk_id:
                        doc_id = chunk_id.rsplit(":", 1)[0]
                        document_ids.add(doc_id)
                
                meta = {
                    "document_count": len(document_ids),
                    "chunk_count": len(chunk_ids),
                    "last_updated": datetime.now().isoformat()
                }
                
                # 写入缓存
                if self.redis_service:
                    try:
                        self.redis_service.set_collection_meta(
                            str(self.user_id),
                            meta,
                            ttl=config.REDIS_CACHE_TTL_COLLECTION_META  # 使用配置常量
                        )
                    except Exception:
                        pass
                
                return meta
        finally:
            release_collection_lock(self.collection_name)
