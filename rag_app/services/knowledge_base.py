import os
from threading import Lock, RLock
import uuid
from datetime import datetime
from typing import BinaryIO

from langchain_chroma import Chroma

from rag_app import config
from rag_app.loaders.document_extractors import extract_text_from_file

DUPLICATE_MESSAGE = "文件已经处理过了"
_collection_lock_guard = Lock()
_collection_locks: dict[str, RLock] = {}


def get_collection_lock(collection_name: str) -> RLock:
    with _collection_lock_guard:
        lock = _collection_locks.get(collection_name)
        if lock is None:
            lock = RLock()
            _collection_locks[collection_name] = lock
        return lock


class KnowledgeBaseService(object):

    def __init__(self, user_id: str | None = None):
        self.user_id = user_id
        self.collection_name = config.build_user_collection_name(user_id)
        self.chroma = Chroma(
            **config.build_chroma_kwargs(
                collection_name=self.collection_name,
                embedding_function=config.OLLAMA_EMBEDDING_FUNCTION,
            )
        )
        self.spliter = config.TEXT_SPLITTER

    def upload_by_str(self, data: str, filename: str):
        with get_collection_lock(self.collection_name):
            return self._save_document_text(
                text=data,
                filename=filename,
                content_sha256=None,
            )

    def upload_by_file(
        self,
        file_source: bytes | BinaryIO,
        filename: str,
        *,
        content_sha256: str | None = None,
    ):
        text = extract_text_from_file(file_source, filename)
        with get_collection_lock(self.collection_name):
            return self._save_document_text(
                text=text,
                filename=filename,
                content_sha256=content_sha256,
            )

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

        with get_collection_lock(self.collection_name):
            result = self.chroma.get(where={"content_sha256": content_sha256})
            chunk_ids = [str(item) for item in result.get("ids", [])]

            if chunk_ids:
                self.chroma.delete(ids=chunk_ids)
            return len(chunk_ids)

    def delete_all_documents(self) -> int:
        with get_collection_lock(self.collection_name):
            result = self.chroma.get()
            chunk_ids = [str(item) for item in result.get("ids", [])]
            if chunk_ids:
                self.chroma.delete(ids=chunk_ids)
            return len(chunk_ids)

    def delete_document(
        self,
        document_id: str | None = None,
    ) -> dict:
        if not document_id:
            raise ValueError("旧知识库记录缺少向量文档标识，无法安全删除，请重新导入后再删除。")

        with get_collection_lock(self.collection_name):
            result = self.chroma.get(where={"document_id": document_id})
            chunk_ids = [str(item) for item in result.get("ids", [])]

            if chunk_ids:
                self.chroma.delete(ids=chunk_ids)

        return {
            "deleted_chunks": len(chunk_ids),
            "message": f"已删除 {len(chunk_ids)} 个知识片段",
        }
