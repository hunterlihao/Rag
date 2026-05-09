"""
统一异常处理模块
定义项目中使用的所有自定义异常类
"""
from typing import Any


class RagBaseException(Exception):
    """RAG项目基础异常类"""
    def __init__(self, message: str, code: str = "RAG_ERROR", details: dict[str, Any] | None = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(RagBaseException):
    """数据验证错误"""
    def __init__(self, message: str, field: str | None = None, details: dict[str, Any] | None = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class AuthenticationError(RagBaseException):
    """认证错误"""
    def __init__(self, message: str = "认证失败", details: dict[str, Any] | None = None):
        super().__init__(message, code="AUTHENTICATION_ERROR", details=details)


class AuthorizationError(RagBaseException):
    """授权错误"""
    def __init__(self, message: str = "权限不足", details: dict[str, Any] | None = None):
        super().__init__(message, code="AUTHORIZATION_ERROR", details=details)


class ResourceNotFoundError(RagBaseException):
    """资源不存在错误"""
    def __init__(self, resource_type: str, resource_id: str | None = None):
        message = f"{resource_type}不存在"
        if resource_id:
            message += f": {resource_id}"
        super().__init__(message, code="RESOURCE_NOT_FOUND", details={
            "resource_type": resource_type,
            "resource_id": resource_id
        })


class RateLimitError(RagBaseException):
    """速率限制错误"""
    def __init__(self, message: str, retry_after: int | None = None):
        details = {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(message, code="RATE_LIMIT_EXCEEDED", details=details)


class FileUploadError(RagBaseException):
    """文件上传错误"""
    def __init__(self, message: str, filename: str | None = None, details: dict[str, Any] | None = None):
        details = details or {}
        if filename:
            details["filename"] = filename
        super().__init__(message, code="FILE_UPLOAD_ERROR", details=details)


class FileValidationError(FileUploadError):
    """文件验证错误"""
    def __init__(self, message: str, filename: str | None = None, validation_type: str | None = None):
        details = {}
        if validation_type:
            details["validation_type"] = validation_type
        super().__init__(message, filename=filename, details=details)


class StorageError(RagBaseException):
    """存储错误(数据库、向量库等)"""
    def __init__(self, message: str, storage_type: str | None = None, details: dict[str, Any] | None = None):
        details = details or {}
        if storage_type:
            details["storage_type"] = storage_type
        super().__init__(message, code="STORAGE_ERROR", details=details)


class VectorStoreError(StorageError):
    """向量库错误"""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, storage_type="vector_store", details=details)


class CacheError(RagBaseException):
    """缓存错误"""
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="CACHE_ERROR", details=details)


class ConfigurationError(RagBaseException):
    """配置错误"""
    def __init__(self, message: str, config_key: str | None = None):
        details = {}
        if config_key:
            details["config_key"] = config_key
        super().__init__(message, code="CONFIGURATION_ERROR", details=details)


class ExternalServiceError(RagBaseException):
    """外部服务错误(Ollama、DashScope等)"""
    def __init__(self, message: str, service_name: str | None = None, details: dict[str, Any] | None = None):
        details = details or {}
        if service_name:
            details["service_name"] = service_name
        super().__init__(message, code="EXTERNAL_SERVICE_ERROR", details=details)
