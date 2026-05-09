"""
优化 #25: 服务容器 - 依赖注入管理
统一管理所有服务实例的生命周期
"""
from typing import Optional
from rag_app.services.redis_service import RedisService
from rag_app.services.auth_service import AuthService
from rag_app.services.workspace_service import WorkspaceService
from rag_app.services.user_service import UserService


class ServiceContainer:
    """服务容器，管理所有服务实例"""
    
    _instance: Optional['ServiceContainer'] = None
    _initialized: bool = False
    
    def __init__(self):
        if self._initialized:
            return
        
        # 创建服务实例
        self.redis_service = RedisService()
        self.auth_service = AuthService(redis_service=self.redis_service)
        self.workspace_service = WorkspaceService(redis_service=self.redis_service)
        self.user_service = UserService(auth_service=self.auth_service)
        
        self._initialized = True
    
    @classmethod
    def get_instance(cls) -> 'ServiceContainer':
        """获取服务容器单例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """重置服务容器（用于测试）"""
        cls._instance = None


# 创建全局服务容器实例
container = ServiceContainer.get_instance()

# 导出服务实例，保持向后兼容
redis_service = container.redis_service
auth_service = container.auth_service
workspace_service = container.workspace_service
user_service = container.user_service
