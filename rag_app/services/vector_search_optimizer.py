"""
向量检索优化服务
提供批量检索、索引预热等优化功能
"""
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_chroma import Chroma

from rag_app import config
from rag_app.exceptions import VectorStoreError

logger = logging.getLogger(__name__)


class VectorSearchOptimizer:
    """向量检索优化器"""
    
    def __init__(self, chroma_client: Chroma, redis_service=None):
        self.chroma = chroma_client
        self.redis_service = redis_service
        self.collection_name = chroma_client._collection.name
    
    def batch_similarity_search(
        self,
        queries: List[str],
        k: int = 5,
        use_cache: bool = True
    ) -> List[List[Dict[str, Any]]]:
        """
        批量相似度检索,减少网络往返
        
        Args:
            queries: 查询文本列表
            k: 每个查询返回的结果数
            use_cache: 是否使用Redis缓存
            
        Returns:
            每个查询的检索结果列表
        """
        results = []
        
        for query in queries:
            # 尝试从缓存获取
            if use_cache and self.redis_service:
                cached = self._get_cached_search(query, k)
                if cached is not None:
                    results.append(cached)
                    continue
            
            # 执行检索
            try:
                docs = self.chroma.similarity_search(query, k=k)
                result = [
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                    }
                    for doc in docs
                ]
                results.append(result)
                
                # 写入缓存
                if use_cache and self.redis_service:
                    self._cache_search_result(query, k, result)
                    
            except Exception as e:
                logger.error(f"检索失败: {query[:50]}..., {e}")
                results.append([])
        
        return results
    
    def parallel_similarity_search(
        self,
        queries: List[str],
        k: int = 5,
        max_workers: int = 4,
        use_cache: bool = True
    ) -> List[List[Dict[str, Any]]]:
        """
        并行相似度检索,提高吞吐量
        
        Args:
            queries: 查询文本列表
            k: 每个查询返回的结果数
            max_workers: 最大并发数
            use_cache: 是否使用Redis缓存
            
        Returns:
            每个查询的检索结果列表
        """
        results = [None] * len(queries)
        
        def search_single(index: int, query: str):
            """单个查询的检索函数"""
            # 尝试从缓存获取
            if use_cache and self.redis_service:
                cached = self._get_cached_search(query, k)
                if cached is not None:
                    return index, cached
            
            # 执行检索
            try:
                docs = self.chroma.similarity_search(query, k=k)
                result = [
                    {
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                    }
                    for doc in docs
                ]
                
                # 写入缓存
                if use_cache and self.redis_service:
                    self._cache_search_result(query, k, result)
                
                return index, result
            except Exception as e:
                logger.error(f"检索失败: {query[:50]}..., {e}")
                return index, []
        
        # 并行执行
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(search_single, i, q): i
                for i, q in enumerate(queries)
            }
            
            for future in as_completed(futures):
                try:
                    index, result = future.result()
                    results[index] = result
                except Exception as e:
                    logger.error(f"并行检索异常: {e}")
        
        return results
    
    def warmup_index(self, sample_queries: List[str] = None, k: int = 5):
        """
        预热向量索引,提前加载常用查询到缓存
        
        Args:
            sample_queries: 样本查询列表,如果为None则使用默认样本
            k: 每个查询返回的结果数
        """
        if sample_queries is None:
            # 使用默认样本查询
            sample_queries = [
                "如何使用",
                "什么是",
                "为什么",
                "怎么办",
                "配置方法",
            ]
        
        logger.info(f"开始预热向量索引,样本查询数: {len(sample_queries)}")
        
        try:
            # 批量检索样本查询
            self.batch_similarity_search(sample_queries, k=k, use_cache=True)
            logger.info("向量索引预热完成")
        except Exception as e:
            logger.error(f"向量索引预热失败: {e}")
    
    def _get_cached_search(self, query: str, k: int) -> List[Dict[str, Any]] | None:
        """从Redis获取缓存的检索结果"""
        try:
            cache_key = f"{query}:k{k}"
            return self.redis_service.get_vector_search(self.collection_name, cache_key)
        except Exception as e:
            logger.debug(f"获取检索缓存失败: {e}")
            return None
    
    def _cache_search_result(self, query: str, k: int, result: List[Dict[str, Any]]):
        """将检索结果写入Redis缓存"""
        try:
            cache_key = f"{query}:k{k}"
            self.redis_service.set_vector_search(
                self.collection_name,
                cache_key,
                result,
                ttl=config.REDIS_CACHE_TTL_VECTOR_SEARCH
            )
        except Exception as e:
            logger.debug(f"写入检索缓存失败: {e}")
    
    def invalidate_cache(self):
        """清除所有检索缓存"""
        if self.redis_service:
            try:
                self.redis_service.invalidate_vector_search(self.collection_name)
                logger.info(f"已清除集合 {self.collection_name} 的检索缓存")
            except Exception as e:
                logger.error(f"清除检索缓存失败: {e}")
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息
        
        Returns:
            统计信息字典
        """
        try:
            collection = self.chroma._collection
            count = collection.count()
            
            # 获取样本数据
            sample = collection.peek(limit=1)
            
            stats = {
                "collection_name": self.collection_name,
                "document_count": count,
                "has_data": count > 0,
            }
            
            if sample and sample.get("ids"):
                stats["sample_id"] = sample["ids"][0]
            
            return stats
        except Exception as e:
            logger.error(f"获取集合统计信息失败: {e}")
            return {
                "collection_name": self.collection_name,
                "error": str(e)
            }
