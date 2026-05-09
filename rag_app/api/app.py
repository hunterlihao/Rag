import hashlib
import io
import json
import logging
import re
import time
import uuid
import asyncio
import csv
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event, Lock

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy.orm import Session

from rag_app import config
from rag_app.exceptions import FileValidationError
from rag_app.services.service_container import (
    redis_service,
    auth_service,
    workspace_service,
    user_service,
)
from rag_app.services.knowledge_base import DUPLICATE_MESSAGE, KnowledgeBaseService
from rag_app.services.rag_service import RagService
from rag_app.storage.database import SessionLocal, get_db, init_database
from rag_app.storage.models import User
from rag_app.utils.logging_config import get_request_id, reset_log_context, set_log_context
from rag_app.validators import validate_upload_file
bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def normalize_email(value: str) -> str:
    normalized_email = value.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        raise ValueError("邮箱格式不正确。")
    return normalized_email


def normalize_required_text(value: str, field_name: str) -> str:
    normalized_value = value.strip()
    if not normalized_value:
        raise ValueError(f"{field_name}不能为空。")
    return normalized_value


class ApiRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(ApiRequestModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_required_text(value, "昵称")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class LoginRequest(ApiRequestModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class ForgotPasswordRequest(ApiRequestModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=255)
    new_password: str = Field(..., min_length=6, max_length=128)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_required_text(value, "用户名")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class ProfileUpdateRequest(ApiRequestModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=255)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_required_text(value, "昵称")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class PasswordUpdateRequest(ApiRequestModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


class AdminUserCreateRequest(ApiRequestModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    is_admin: StrictBool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_required_text(value, "昵称")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class AdminUserUpdateRequest(ApiRequestModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(default="", max_length=128)
    is_admin: StrictBool

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_required_text(value, "昵称")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class AskRequest(ApiRequestModel):
    prompt: str = Field(..., min_length=1, max_length=config.MAX_PROMPT_CHARS)
    answer_mode: str = Field(default=config.ANSWER_MODE_AUTO)
    chat_model_id: str = Field(default=config.DEFAULT_CHAT_MODEL_ID, max_length=160)
    answer_request_id: str = Field(default="", max_length=80)

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        return normalize_required_text(value, "问题")

    @field_validator("answer_mode")
    @classmethod
    def validate_answer_mode(cls, value: str) -> str:
        answer_mode = value.strip().lower()
        if answer_mode not in config.SUPPORTED_ANSWER_MODES:
            raise ValueError("回答模式不正确。")
        return answer_mode

    @field_validator("chat_model_id")
    @classmethod
    def validate_chat_model_id(cls, value: str) -> str:
        chat_model_id = value.strip()
        if not chat_model_id:
            return config.DEFAULT_CHAT_MODEL_ID
        if chat_model_id not in config.CHAT_MODEL_OPTION_BY_ID:
            raise ValueError("问答模型不正确。")
        return chat_model_id

    @field_validator("answer_request_id")
    @classmethod
    def validate_answer_request_id(cls, value: str) -> str:
        return value.strip()


class StopAnswerRequest(ApiRequestModel):
    answer_request_id: str = Field(default="", max_length=80)

    @field_validator("answer_request_id")
    @classmethod
    def validate_answer_request_id(cls, value: str) -> str:
        return value.strip()


class BatchDeleteUploadsRequest(ApiRequestModel):
    upload_ids: list[str] = Field(
        ...,
        min_length=1,
        max_length=config.MAX_BATCH_DELETE_UPLOADS,
    )

    @field_validator("upload_ids")
    @classmethod
    def validate_upload_ids(cls, value: list[str]) -> list[str]:
        normalized_ids = []
        for upload_id in value:
            normalized_id = str(upload_id).strip()
            if not normalized_id:
                continue
            if len(normalized_id) > 64:
                raise ValueError("知识库文件 ID 格式不正确。")
            if normalized_id not in normalized_ids:
                normalized_ids.append(normalized_id)
        if not normalized_ids:
            raise ValueError("请至少选择一个知识库文件。")
        return normalized_ids


def build_error(status_code: int, message: str):
    raise HTTPException(status_code=status_code, detail=message)


def build_upload_result_payload(
    *,
    order: int,
    filename: str,
    content_type: str,
    size_bytes: int,
    status_value: str,
    message: str,
    uploader_name: str,
    duplicate: bool = False,
):
    return {
        "order": order,
        "id": f"temp-{order}-{filename}",
        "name": filename,
        "type": content_type,
        "size": size_bytes,
        "status": status_value,
        "message": message,
        "duplicate": duplicate,
        "uploaded_at": None,
        "uploader_name": uploader_name,
    }


def get_upload_size(upload: UploadFile) -> int:
    file_obj = upload.file
    current_position = file_obj.tell()
    file_obj.seek(0, 2)
    size_bytes = int(file_obj.tell())
    file_obj.seek(current_position)
    return size_bytes


def calculate_upload_sha256(upload: UploadFile) -> str:
    file_obj = upload.file
    file_obj.seek(0)
    sha256_obj = hashlib.sha256()
    while chunk := file_obj.read(config.UPLOAD_STREAM_CHUNK_SIZE):
        sha256_obj.update(chunk)
    file_obj.seek(0)
    return sha256_obj.hexdigest()


def encode_stream_event(event_type: str, **payload) -> str:
    return json.dumps(
        {
            "type": event_type,
            **payload,
        },
        ensure_ascii=False,
    ) + "\n"


class AnswerRunRegistry:
    def __init__(self):
        self._lock = Lock()
        self._runs: dict[tuple[str, str], dict[str, object]] = {}

    @staticmethod
    def build_key(user_id: str, session_id: str) -> tuple[str, str]:
        return (str(user_id), str(session_id))

    def start(self, user_id: str, session_id: str, request_id: str | None = None) -> tuple[str, Event]:
        event = Event()
        normalized_request_id = str(request_id or "").strip() or str(uuid.uuid4())
        key = self.build_key(user_id, session_id)
        with self._lock:
            existing_run = self._runs.get(key)
            if existing_run is not None:
                existing_event = existing_run.get("event")
                if isinstance(existing_event, Event):
                    existing_event.set()
            self._runs[key] = {
                "request_id": normalized_request_id,
                "event": event,
            }
        return normalized_request_id, event

    def stop(self, user_id: str, session_id: str, request_id: str | None = None) -> bool:
        key = self.build_key(user_id, session_id)
        normalized_request_id = str(request_id or "").strip()
        with self._lock:
            current_run = self._runs.get(key)
            if current_run is None:
                return False
            if normalized_request_id and current_run.get("request_id") != normalized_request_id:
                return False
            event = current_run.get("event")
            if not isinstance(event, Event):
                return False
            event.set()
            return True

    def finish(self, user_id: str, session_id: str, event: Event):
        key = self.build_key(user_id, session_id)
        with self._lock:
            current_run = self._runs.get(key)
            if current_run is not None and current_run.get("event") is event:
                self._runs.pop(key, None)


answer_run_registry = AnswerRunRegistry()


class WebSocketManager:
    """优化 #12: WebSocket 连接管理器，用于推送上传进度
    改进:
    1. 使用信号量限制并发心跳任务
    2. 添加连接健康检查
    3. 优化内存使用
    """
    MAX_CONNECTIONS = 1000  # 最大连接数
    HEARTBEAT_INTERVAL = 30  # 心跳间隔(秒)
    HEARTBEAT_TIMEOUT = 90  # 心跳超时时间(秒)
    MAX_HEARTBEAT_TASKS = 100  # 最大并发心跳任务数
    
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._lock = Lock()
        self._heartbeat_tasks: dict[str, asyncio.Task] = {}  # 心跳任务
        self._last_activity: dict[str, float] = {}  # 最后活动时间
        self._heartbeat_semaphore = asyncio.Semaphore(self.MAX_HEARTBEAT_TASKS)  # 限制并发
    
    async def connect(self, websocket: WebSocket, user_id: str):
        # 注意: 不再调用websocket.accept(),因为端点函数已经在认证前accept了
        # 连接数检查也在端点中完成了,这里只负责管理连接
        with self._lock:
            # 如果已有连接，先关闭
            if user_id in self._connections:
                try:
                    await self._connections[user_id].close()
                except Exception:
                    pass
                # 清理旧的心跳任务
                if user_id in self._heartbeat_tasks:
                    self._heartbeat_tasks[user_id].cancel()
            
            self._connections[user_id] = websocket
            self._last_activity[user_id] = time.time()
        
        # 启动心跳任务
        self._heartbeat_tasks[user_id] = asyncio.create_task(
            self._heartbeat_loop(user_id, websocket)
        )
    
    async def _heartbeat_loop(self, user_id: str, websocket: WebSocket):
        """心跳循环,定期发送ping检测连接状态"""
        try:
            while True:
                await asyncio.sleep(self.HEARTBEAT_INTERVAL)
                
                # 检查是否超时
                with self._lock:
                    last_active = self._last_activity.get(user_id, 0)
                
                if time.time() - last_active > self.HEARTBEAT_TIMEOUT:
                    logger.info("WebSocket心跳超时,断开连接: %s", user_id)
                    self.disconnect(user_id)
                    break
                
                # 发送心跳(使用ping帧而非JSON消息,更轻量)
                try:
                    await websocket.send_bytes(b'\x89\x00')  # WebSocket ping帧
                except Exception:
                    logger.debug("WebSocket心跳发送失败(连接已断开): %s", user_id)
                    self.disconnect(user_id)
                    break
        except asyncio.CancelledError:
            pass  # 任务被取消,正常退出
        except Exception as e:
            logger.debug("WebSocket心跳异常: %s, %s", user_id, str(e))
            self.disconnect(user_id)

    def disconnect(self, user_id: str):
        with self._lock:
            # 取消心跳任务
            if user_id in self._heartbeat_tasks:
                self._heartbeat_tasks[user_id].cancel()
                self._heartbeat_tasks.pop(user_id, None)
            
            self._connections.pop(user_id, None)
            self._last_activity.pop(user_id, None)
    
    def update_activity(self, user_id: str):
        """更新最后活动时间"""
        with self._lock:
            self._last_activity[user_id] = time.time()

    async def send_upload_progress(self, user_id: str, progress_data: dict):
        """发送上传进度到指定用户"""
        with self._lock:
            websocket = self._connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json({
                    "type": "upload_progress",
                    **progress_data,
                })
                self.update_activity(user_id)
            except Exception:
                self.disconnect(user_id)

    async def send_upload_complete(self, user_id: str, complete_data: dict):
        """发送上传完成通知到指定用户"""
        with self._lock:
            websocket = self._connections.get(user_id)
        if websocket:
            try:
                await websocket.send_json({
                    "type": "upload_complete",
                    **complete_data,
                })
                self.update_activity(user_id)
            except Exception:
                self.disconnect(user_id)
    
    def get_connection_count(self) -> int:
        """获取当前连接数"""
        with self._lock:
            return len(self._connections)
    
    async def cleanup_all(self):
        """清理所有连接(用于服务关闭)"""
        with self._lock:
            for user_id in list(self._connections.keys()):
                try:
                    if user_id in self._heartbeat_tasks:
                        self._heartbeat_tasks[user_id].cancel()
                    websocket = self._connections.get(user_id)
                    if websocket:
                        await websocket.close()
                except Exception:
                    pass
            self._connections.clear()
            self._heartbeat_tasks.clear()
            self._last_activity.clear()


websocket_manager = WebSocketManager()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    database: Session = Depends(get_db),
):
    if credentials is None:
        build_error(status.HTTP_401_UNAUTHORIZED, "请先登录。")

    try:
        payload = auth_service.decode_access_token(credentials.credentials)
        user_id = str(payload.get("sub", "")).strip()
    except Exception:
        build_error(status.HTTP_401_UNAUTHORIZED, "登录状态无效，请重新登录。")

    if auth_service.is_token_revoked(payload):
        build_error(status.HTTP_401_UNAUTHORIZED, "登录状态已失效，请重新登录。")

    user = auth_service.get_user(database, user_id)
    if user is None:
        build_error(status.HTTP_401_UNAUTHORIZED, "当前账号不存在，请重新登录。")
    if not auth_service.is_token_current(payload, user):
        build_error(status.HTTP_401_UNAUTHORIZED, "登录状态已过期,请重新登录。")
    return user


def delete_upload_entry(database: Session, user, upload):
    """删除上传条目 - 同时删除向量库中的文档和数据库中的记录"""
    kb_service = KnowledgeBaseService(user.id, redis_service=redis_service)
    delete_result = kb_service.delete_document(document_id=upload.vector_doc_id)
    workspace_service.delete_upload_with_registry(database, upload)
    return delete_result


def get_current_admin(user=Depends(get_current_user)):
    if not user.is_admin:
        build_error(status.HTTP_403_FORBIDDEN, "当前账号没有管理员权限。")
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Application startup started.",
        extra={
            "event": "app.startup.started",
            "app_env": config.APP_ENV,
            "chroma_mode": config.CHROMA_MODE,
            "chat_model_provider": config.ACTIVE_CHAT_MODEL_PROVIDER,
            "chat_model": config.ACTIVE_CHAT_MODEL_NAME,
            "embedding_model": config.EMBEDDING_MODEL_NAME,
        },
    )
    config.validate_server_config()
    init_database()
    redis_service.ping()
    startup_db = SessionLocal()
    try:
        auth_service.ensure_admin_account(startup_db)
        workspace_service.cleanup_stale_upload_registries(startup_db)
    finally:
        startup_db.close()
    
    # 初始化RagService
    app.state.rag_service = RagService(redis_service=redis_service)
    
    # 启动RabbitMQ消费者(如果启用)
    if config.RABBITMQ_ENABLED:
        try:
            from rag_app.services.queue_service import get_queue_service
            queue_service = get_queue_service()
            
            # 重试连接(最多3次)
            connected = False
            for attempt in range(3):
                if await queue_service.connect():
                    connected = True
                    break
                logger.warning(f"RabbitMQ连接失败,重试 {attempt + 1}/3...")
                await asyncio.sleep(2)
            
            if connected:
                # 启动消费者处理上传任务
                await queue_service.start_consumer(async_process_upload_message)
                app.state.queue_service = queue_service
                logger.info("RabbitMQ消费者已启动")
            else:
                logger.warning("RabbitMQ连接失败,文件上传将使用BackgroundTasks处理")
        except Exception as e:
            logger.error(f"RabbitMQ初始化失败: {e}")
    
    logger.info("Application startup completed.", extra={"event": "app.startup.completed"})
    try:
        yield
    finally:
        # 清理所有WebSocket连接
        await websocket_manager.cleanup_all()
        
        # 关闭RabbitMQ连接
        if config.RABBITMQ_ENABLED and hasattr(app.state, 'queue_service'):
            await app.state.queue_service.close()
        
        logger.info("Application shutdown completed.", extra={"event": "app.shutdown.completed"})


def create_app() -> FastAPI:
    print("[DEBUG] create_app() 开始执行")
    app = FastAPI(
        title="RAG API",
        version="0.1.0",
        lifespan=lifespan,
    )
    print("[DEBUG] FastAPI 实例创建成功")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.API_CORS_ORIGINS,
        allow_origin_regex=config.API_CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 安全漏洞修复6: 请求体大小限制中间件
    @app.middleware("http")
    async def limit_request_size(request: Request, call_next):
        """限制请求体大小,防止DoS攻击"""
        # 只检查POST/PUT/PATCH请求
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("content-length")
            if content_length:
                # 限制为100MB(适应文件上传需求)
                max_size = 100 * 1024 * 1024  # 100MB
                if int(content_length) > max_size:
                    return JSONResponse(
                        status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
                        content={"detail": "请求体过大,最大支持100MB"},
                        headers={"X-Request-ID": request.headers.get("x-request-id") or str(uuid.uuid4())},
                    )
        return await call_next(request)

    @app.middleware("http")
    async def request_logging_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        client_host = auth_service.resolve_client_host(request)
        context_tokens = set_log_context(
            request_id=request_id,
            client_ip=client_host,
        )
        started_at = time.perf_counter()
        status_code = 500
        response = None

        try:
            credentials = await bearer_scheme(request)
            if credentials is not None:
                try:
                    token_payload = auth_service.decode_access_token(credentials.credentials)
                    context_tokens.update(
                        set_log_context(user_id=str(token_payload.get("sub", "")).strip() or "-")
                    )
                except Exception:
                    context_tokens.update(set_log_context(user_id="-"))

            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            logger.exception(
                "Unhandled request error.",
                extra={
                    "event": "http.request.unhandled_error",
                    "method": request.method,
                    "path": request.url.path,
                    "query": request.url.query,
                },
            )
            raise
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            log_extra = {
                "event": "http.request.completed",
                "method": request.method,
                "path": request.url.path,
                "query": request.url.query,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "user_agent": request.headers.get("user-agent", ""),
            }
            if response is not None:
                response.headers["X-Request-ID"] = request_id
            if status_code >= 500:
                logger.error("HTTP request failed.", extra={**log_extra, "event": "http.request.failed"})
            elif duration_ms >= config.LOG_SLOW_REQUEST_MS:
                logger.warning("Slow HTTP request.", extra={**log_extra, "event": "http.request.slow"})
            elif config.LOG_ACCESS_ENABLED:
                logger.info("HTTP request completed.", extra=log_extra)
            reset_log_context(context_tokens)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.warning(
            "Request validation failed.",
            extra={
                "event": "http.request.validation_failed",
                "method": request.method,
                "path": request.url.path,
                "error_count": len(exc.errors()),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "请求参数格式不正确，请检查输入内容。"},
            headers={"X-Request-ID": get_request_id()},
        )

    @app.get("/api/meta")
    def get_meta():
        return {
            "model_provider": config.ACTIVE_CHAT_MODEL_PROVIDER,
            "chat_model": config.ACTIVE_CHAT_MODEL_NAME,
            "default_chat_model_id": config.DEFAULT_CHAT_MODEL_ID,
            "chat_models": config.CHAT_MODEL_OPTIONS,
            "embedding_model": config.EMBEDDING_MODEL_NAME,
            "supported_upload_extensions": config.SUPPORTED_UPLOAD_EXTENSIONS,
            "startup_error": None,
        }

    @app.websocket("/ws/uploads")
    async def websocket_upload_progress(websocket: WebSocket):
        """WebSocket 端点,用于推送上传进度
        
        安全修复: Token不再通过URL参数传递,改为握手后第一条消息传递
        防止Token被记录在服务器日志、代理日志、浏览器历史中
        """
        database = SessionLocal()
        try:
            # 0. 先检查连接数限制(在accept之前)
            if websocket_manager.get_connection_count() >= websocket_manager.MAX_CONNECTIONS:
                # 连接数已满,直接拒绝,不accept
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason=f"WebSocket连接数已达上限({websocket_manager.MAX_CONNECTIONS})"
                )
                return
            
            # 1. 接受WebSocket连接
            await websocket.accept()
            
            # 2. 等待客户端发送认证消息(超时30秒)
            try:
                auth_message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=config.WS_AUTH_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION, 
                    reason="认证超时:未在规定时间内发送认证消息"
                )
                return
            
            # 3. 解析认证消息
            try:
                auth_data = json.loads(auth_message)
                if auth_data.get("type") != "auth":
                    raise ValueError("非认证消息")
                token = auth_data.get("token", "").strip()
                if not token:
                    raise ValueError("Token为空")
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION, 
                    reason=f"认证失败:消息格式错误 - {str(e)}"
                )
                return
            
            # 4. 完整的Token验证逻辑
            try:
                payload = auth_service.decode_access_token(token)
            except Exception:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="认证失败:Token无效")
                return
                
            user_id = str(payload.get("sub", "")).strip()
            if not user_id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="认证失败:Token缺少用户标识")
                return
                
            # 5. 检查Token是否已吊销
            if auth_service.is_token_revoked(payload):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="认证失败:Token已吊销")
                return
                
            # 6. 检查用户是否存在
            user = auth_service.get_user(database, user_id)
            if user is None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="认证失败:用户不存在")
                return
                
            # 7. 检查Token版本是否匹配
            if not auth_service.is_token_current(payload, user):
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="认证失败:Token已过期")
                return
            
            # 8. 发送认证成功消息
            await websocket.send_json({"type": "auth_success", "message": "认证成功"})
                
            # 9. 验证通过,建立连接
            await websocket_manager.connect(websocket, user_id)
            try:
                while True:
                    # 接收消息(用于保持连接活跃)
                    try:
                        message = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=websocket_manager.HEARTBEAT_TIMEOUT
                        )
                        # 更新活动时间
                        websocket_manager.update_activity(user_id)
                        
                        # 处理pong响应和普通消息
                        try:
                            data = json.loads(message)
                            if data.get("type") == "pong":
                                logger.debug("收到WebSocket pong: %s", user_id)
                                continue
                        except (json.JSONDecodeError, KeyError):
                            pass  # 忽略非JSON消息
                    except asyncio.TimeoutError:
                        # 超时,这是正常的,客户端可能暂时空闲
                        logger.debug("WebSocket接收超时(客户端空闲): %s", user_id)
                        # 不break,继续等待下一次消息
                        continue
            except WebSocketDisconnect:
                websocket_manager.disconnect(user_id)
        except RuntimeError as e:
            # 连接数限制等错误
            logger.warning("WebSocket连接被拒绝: %s", str(e))
            try:
                await websocket.close(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason=str(e)
                )
            except Exception:
                pass
        finally:
            database.close()

    @app.post("/api/auth/register")
    def register(
        payload: RegisterRequest,
        request: Request,
        database: Session = Depends(get_db),
    ):
        client_host = auth_service.resolve_client_host(request)
        register_allowed, retry_after_seconds = auth_service.register_rate_limit_status(
            client_host
        )
        if not register_allowed:
            build_error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"注册尝试过于频繁，请在 {retry_after_seconds or config.REGISTER_RATE_LIMIT_WINDOW_SECONDS} 秒后重试。",
            )

        try:
            user = auth_service.register_user(
                database,
                name=payload.name,
                email=payload.email,
                password=payload.password,
            )
        except ValueError as exc:
            auth_service.record_register_attempt(client_host)
            build_error(status.HTTP_400_BAD_REQUEST, str(exc))

        auth_service.record_register_attempt(client_host)

        return {
            "access_token": auth_service.create_access_token(user),
            "token_type": "bearer",
            "user": auth_service.serialize_user(user),
        }

    @app.post("/api/auth/login")
    def login(
        payload: LoginRequest,
        request: Request,
        database: Session = Depends(get_db),
    ):
        email = payload.email
        client_host = auth_service.resolve_client_host(request)
        login_allowed, retry_after_seconds = auth_service.login_rate_limit_status(
            client_host,
            email,
        )
        if not login_allowed:
            logger.warning(
                "Login rejected by rate limit.",
                extra={"event": "auth.login.rate_limited", "email_hash": hashlib.sha256(email.encode("utf-8")).hexdigest()[:12]},
            )
            build_error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"登录尝试过于频繁，请在 {retry_after_seconds or config.LOGIN_RATE_LIMIT_WINDOW_SECONDS} 秒后重试。",
            )

        try:
            user = auth_service.authenticate_user(
                database,
                email=email,
                password=payload.password,
            )
        except ValueError as exc:
            auth_service.record_login_failure(client_host, email)
            logger.warning(
                "Login failed.",
                extra={"event": "auth.login.failed", "email_hash": hashlib.sha256(email.encode("utf-8")).hexdigest()[:12]},
            )
            build_error(status.HTTP_400_BAD_REQUEST, str(exc))

        auth_service.clear_login_failures(client_host, email)
        logger.info("Login succeeded.", extra={"event": "auth.login.succeeded", "login_user_id": user.id})

        return {
            "access_token": auth_service.create_access_token(user),
            "token_type": "bearer",
            "user": auth_service.serialize_user(user),
        }

    @app.post("/api/auth/logout")
    def logout(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        user=Depends(get_current_user),
    ):
        if credentials is None:
            build_error(status.HTTP_401_UNAUTHORIZED, "请先登录。")

        try:
            payload = auth_service.decode_access_token(credentials.credentials)
            auth_service.revoke_access_token(payload)
        except Exception:
            pass

        logger.info("Logout completed.", extra={"event": "auth.logout", "logout_user_id": user.id})
        return {
            "message": f"{user.name} 已退出登录。",
        }

    @app.post("/api/auth/forgot-password")
    def forgot_password(
        payload: ForgotPasswordRequest,
        request: Request,
        database: Session = Depends(get_db),
    ):
        client_host = auth_service.resolve_client_host(request)
        forgot_allowed, retry_after_seconds = auth_service.register_rate_limit_status(client_host)
        if not forgot_allowed:
            build_error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                f"操作过于频繁，请在 {retry_after_seconds or config.REGISTER_RATE_LIMIT_WINDOW_SECONDS} 秒后重试。",
            )

        user = auth_service.find_user_by_email(database, payload.email)
        if user is None:
            auth_service.record_register_attempt(client_host)
            logger.warning(
                "Password reset failed: email not found.",
                extra={"event": "auth.forgot_password.failed", "email_hash": hashlib.sha256(payload.email.encode("utf-8")).hexdigest()[:12]},
            )
            build_error(status.HTTP_400_BAD_REQUEST, "用户名或邮箱不匹配，请检查后重试。")

        if user.name.strip() != payload.name.strip():
            auth_service.record_register_attempt(client_host)
            logger.warning(
                "Password reset failed: name mismatch.",
                extra={"event": "auth.forgot_password.failed", "user_id": user.id},
            )
            build_error(status.HTTP_400_BAD_REQUEST, "用户名或邮箱不匹配，请检查后重试。")

        if len(payload.new_password) < 6:
            build_error(status.HTTP_400_BAD_REQUEST, "新密码至少需要 6 位。")

        user.password_hash = auth_service.hash_password(payload.new_password)
        user_service.bump_token_version(user)
        database.add(user)
        database.commit()

        logger.info("Password reset succeeded.", extra={"event": "auth.forgot_password.succeeded", "user_id": user.id})
        return {"message": "密码重置成功，请使用新密码登录。"}

    @app.get("/api/auth/me")
    def me(user=Depends(get_current_user)):
        return {"user": auth_service.serialize_user(user)}

    @app.put("/api/users/me")
    def update_my_profile(
        payload: ProfileUpdateRequest,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        try:
            updated_user = user_service.update_profile(
                database,
                user,
                name=payload.name,
                email=payload.email,
            )
        except ValueError as exc:
            build_error(status.HTTP_400_BAD_REQUEST, str(exc))

        return {
            "message": "个人信息已更新。",
            "user": auth_service.serialize_user(updated_user),
        }

    @app.put("/api/users/me/password")
    def update_my_password(
        payload: PasswordUpdateRequest,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        try:
            user_service.change_password(
                database,
                user,
                current_password=payload.current_password,
                new_password=payload.new_password,
            )
        except ValueError as exc:
            build_error(status.HTTP_400_BAD_REQUEST, str(exc))

        return {
            "message": "密码已更新，请重新登录。",
        }

    @app.get("/api/admin/users")
    def list_admin_users(
        keyword: str = "",
        admin=Depends(get_current_admin),
        database: Session = Depends(get_db),
    ):
        users = user_service.list_users(database, keyword)
        return {
            "users": [auth_service.serialize_user(item) for item in users],
            "current_admin_id": admin.id,
        }

    @app.post("/api/admin/users")
    def create_admin_user(
        payload: AdminUserCreateRequest,
        admin=Depends(get_current_admin),
        database: Session = Depends(get_db),
    ):
        try:
            created_user = user_service.create_user(
                database,
                name=payload.name,
                email=payload.email,
                password=payload.password,
                is_admin=payload.is_admin,
            )
        except ValueError as exc:
            build_error(status.HTTP_400_BAD_REQUEST, str(exc))

        return {
            "message": f"已创建用户「{created_user.name}」。",
            "user": auth_service.serialize_user(created_user),
        }

    @app.put("/api/admin/users/{user_id}")
    def update_admin_user(
        user_id: str,
        payload: AdminUserUpdateRequest,
        admin=Depends(get_current_admin),
        database: Session = Depends(get_db),
    ):
        try:
            target_user = user_service.require_user(database, user_id)
            updated_user = user_service.admin_update_user(
                database,
                admin,
                target_user,
                name=payload.name,
                email=payload.email,
                is_admin=payload.is_admin,
                password=payload.password,
            )
        except ValueError as exc:
            build_error(status.HTTP_400_BAD_REQUEST, str(exc))
        except PermissionError as exc:
            build_error(status.HTTP_403_FORBIDDEN, str(exc))

        response_payload = {
            "message": f"已更新用户「{updated_user.name}」。",
            "user": auth_service.serialize_user(updated_user),
        }
        if updated_user.id == admin.id:
            response_payload["access_token"] = auth_service.create_access_token(updated_user)
            response_payload["token_type"] = "bearer"
        return response_payload

    @app.delete("/api/admin/users/{user_id}")
    def delete_admin_user(
        user_id: str,
        admin=Depends(get_current_admin),
        database: Session = Depends(get_db),
    ):
        try:
            target_user = user_service.require_user(database, user_id)
            target_name = target_user.name
            user_service.delete_user(database, admin, user_id)
        except ValueError as exc:
            build_error(status.HTTP_400_BAD_REQUEST, str(exc))
        except PermissionError as exc:
            build_error(status.HTTP_403_FORBIDDEN, str(exc))

        return {
            "message": f"已删除用户「{target_name}」。",
        }

    @app.get("/api/sessions")
    def list_sessions(user=Depends(get_current_user), database: Session = Depends(get_db)):
        return {"sessions": workspace_service.list_sessions(database, user)}

    @app.post("/api/sessions")
    def create_session(user=Depends(get_current_user), database: Session = Depends(get_db)):
        session = workspace_service.create_session(database, user)
        return {"session": workspace_service.get_session_detail(database, user, session.id)}

    @app.get("/api/sessions/{session_id}")
    def get_session(
        session_id: str,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        try:
            return {"session": workspace_service.get_session_detail(database, user, session_id)}
        except ValueError as exc:
            build_error(status.HTTP_404_NOT_FOUND, str(exc))

    @app.delete("/api/sessions/{session_id}")
    def delete_session(
        session_id: str,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        try:
            deleted_session = workspace_service.delete_session(database, user, session_id)
        except ValueError as exc:
            build_error(status.HTTP_404_NOT_FOUND, str(exc))
        except Exception:
            logger.exception("Failed to delete chat session.")
            build_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "删除会话失败，请稍后重试。")

        sessions = workspace_service.list_sessions(database, user)
        return {
            "message": f"已删除会话「{deleted_session.title}」。",
            "deleted_session_id": deleted_session.id,
            "next_session_id": sessions[0]["id"] if sessions else None,
            "sessions": sessions,
        }

    @app.get("/api/sessions/{session_id}/export")
    def export_session(
        session_id: str,
        request: Request,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        """优化 #20: 导出对话记录为 CSV 或 JSON"""
        from rag_app.storage.chat_history import load_session_messages
        
        try:
            session = workspace_service.require_session(database, user, session_id)
        except ValueError as exc:
            build_error(status.HTTP_404_NOT_FOUND, str(exc))
        
        # 获取导出格式参数
        query_params = request.query_params
        export_format = query_params.get("format", "json").lower()
        
        # 加载消息
        messages = load_session_messages(session_id)
        
        if export_format == "csv":
            # CSV 格式导出
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写入表头
            writer.writerow(["角色", "内容", "时间戳"])
            
            # 写入消息
            for msg in messages:
                writer.writerow([
                    "用户" if msg["role"] == "user" else "助手",
                    msg["content"],
                    ""
                ])
            
            # 生成CSV文件
            csv_content = output.getvalue()
            output.close()
            
            filename = f"chat_{session_id[:8]}.csv"
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "text/csv; charset=utf-8-sig",
            }
            return Response(content=csv_content.encode("utf-8-sig"), headers=headers)
        
        else:
            # JSON 格式导出（默认）
            export_data = {
                "session_id": session_id,
                "title": session.title,
                "message_count": len(messages),
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "messages": messages,
            }
            
            json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
            filename = f"chat_{session_id[:8]}.json"
            headers = {
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/json; charset=utf-8",
            }
            return Response(content=json_content.encode("utf-8"), headers=headers)

    @app.post("/api/sessions/{session_id}/ask")
    def ask_session(
        session_id: str,
        payload: AskRequest,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        prompt = payload.prompt

        try:
            session = workspace_service.require_session(database, user, session_id)
        except ValueError as exc:
            build_error(status.HTTP_404_NOT_FOUND, str(exc))

        try:
            assistant_reply, sources = app.state.rag_service.invoke(
                {
                    "input": prompt,
                    "user_id": user.id,
                    "answer_mode": payload.answer_mode,
                    "chat_model_id": payload.chat_model_id,
                },
                {"configurable": {"session_id": session_id}},
            )
            workspace_service.touch_session(database, session, prompt, assistant_reply)
            app.state.rag_service.append_history(session_id, prompt, assistant_reply, sources=sources)
            return {"session": workspace_service.get_session_detail(database, user, session_id), "sources": sources}
        except Exception:
            logger.exception("Failed to generate RAG answer.")
            build_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "生成回答失败，请稍后重试。")

    @app.post("/api/sessions/{session_id}/ask/stream")
    def ask_session_stream(
        session_id: str,
        payload: AskRequest,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        prompt = payload.prompt
        try:
            session = workspace_service.require_session(database, user, session_id)
        except ValueError as exc:
            build_error(status.HTTP_404_NOT_FOUND, str(exc))

        answer_request_id, cancel_event = answer_run_registry.start(
            user.id,
            session_id,
            payload.answer_request_id,
        )
        logger.info(
            "Streaming answer started.",
            extra={
                "event": "rag.answer.stream.started",
                "session_id": session_id,
                "answer_request_id": answer_request_id,
                "answer_mode": payload.answer_mode,
                "chat_model_id": payload.chat_model_id,
                "prompt_length": len(prompt),
            },
        )

        def stream_answer():
            stream_database = SessionLocal()
            assistant_parts: list[str] = []
            persisted = False
            sources_data: list[dict] = []

            def persist_answer():
                nonlocal persisted
                if persisted:
                    return
                assistant_reply = "".join(assistant_parts)
                if cancel_event.is_set() and not assistant_reply.strip():
                    assistant_reply = "已停止回答。"
                app.state.rag_service.append_history(session_id, prompt, assistant_reply, sources=sources_data)
                workspace_service.touch_session(stream_database, stream_session, prompt, assistant_reply)
                persisted = True

            try:
                stream_session = workspace_service.require_session(stream_database, user, session_id)
                for chunk in app.state.rag_service.stream(
                    {
                        "input": prompt,
                        "user_id": user.id,
                        "answer_mode": payload.answer_mode,
                        "chat_model_id": payload.chat_model_id,
                    },
                    {"configurable": {"session_id": session_id}},
                    cancel_checker=cancel_event.is_set,
                ):
                    if cancel_event.is_set():
                        break
                    if isinstance(chunk, dict) and "__sources__" in chunk:
                        sources_data = chunk["__sources__"]
                        yield encode_stream_event("sources", sources=sources_data)
                        continue
                    content = str(chunk or "")
                    if not content:
                        continue
                    assistant_parts.append(content)
                    yield encode_stream_event("delta", content=content)

                persist_answer()
                logger.info(
                    "Streaming answer persisted.",
                    extra={
                        "event": "rag.answer.stream.persisted",
                        "session_id": session_id,
                        "answer_request_id": answer_request_id,
                        "stopped": cancel_event.is_set(),
                        "answer_length": len("".join(assistant_parts)),
                    },
                )
                yield encode_stream_event(
                    "session",
                    session=workspace_service.get_session_detail(stream_database, user, session_id),
                    stopped=cancel_event.is_set(),
                )
            except GeneratorExit:
                cancel_event.set()
                try:
                    persist_answer()
                except Exception:
                    logger.exception(
                        "Failed to persist interrupted RAG answer.",
                        extra={
                            "event": "rag.answer.stream.persist_failed",
                            "session_id": session_id,
                            "answer_request_id": answer_request_id,
                        },
                    )
                raise
            except Exception:
                stream_database.rollback()
                try:
                    if assistant_parts:
                        persist_answer()
                except Exception:
                    logger.exception(
                        "Failed to persist partial RAG answer after stream error.",
                        extra={
                            "event": "rag.answer.stream.partial_persist_failed",
                            "session_id": session_id,
                            "answer_request_id": answer_request_id,
                        },
                    )
                logger.exception(
                    "Failed to stream RAG answer.",
                    extra={
                        "event": "rag.answer.stream.failed",
                        "session_id": session_id,
                        "answer_request_id": answer_request_id,
                    },
                )
                yield encode_stream_event(
                    "error",
                    message="生成回答失败，请稍后重试。",
                )
            finally:
                stream_database.close()
                answer_run_registry.finish(user.id, session_id, cancel_event)

        return StreamingResponse(stream_answer(), media_type="application/x-ndjson")

    @app.post("/api/sessions/{session_id}/ask/stop")
    def stop_session_answer(
        session_id: str,
        payload: StopAnswerRequest,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        try:
            workspace_service.require_session(database, user, session_id)
        except ValueError as exc:
            build_error(status.HTTP_404_NOT_FOUND, str(exc))

        stopped = answer_run_registry.stop(user.id, session_id, payload.answer_request_id)
        logger.info(
            "Stop answer requested.",
            extra={
                "event": "rag.answer.stop.requested",
                "session_id": session_id,
                "answer_request_id": payload.answer_request_id,
                "stopped": stopped,
            },
        )
        return {
            "stopped": stopped,
            "message": "已停止当前回答。" if stopped else "当前没有正在生成的回答。",
        }

    @app.get("/api/uploads")
    def list_uploads(
        request: Request,
        user=Depends(get_current_user), 
        database: Session = Depends(get_db)
    ):
        """优化 #19: 添加搜索功能的上传列表"""
        # 获取搜索参数
        query_params = request.query_params
        search_query = query_params.get("q", "").strip()
        
        # 如果搜索词为空，返回所有
        if not search_query:
            uploads = workspace_service.list_uploads(database, user)
            return {"uploads": uploads, "total": len(uploads)}
        
        # 搜索逻辑：匹配文件名
        all_uploads = workspace_service.list_uploads(database, user)
        filtered_uploads = [
            upload for upload in all_uploads
            if search_query.lower() in upload.get("name", "").lower()
        ]
        
        return {"uploads": filtered_uploads, "total": len(filtered_uploads)}

    @app.post("/api/uploads")
    async def upload_files(
        files: list[UploadFile] = File(...),
        background_tasks: BackgroundTasks = None,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        """
        优化后的文件上传端点
        - 完整的文件验证(扩展名、魔数、大小)
        - 流式处理,避免内存溢出
        - 使用FastAPI BackgroundTasks异步处理
        - WebSocket实时推送进度
        """
        if len(files) > config.MAX_UPLOAD_BATCH_FILES:
            build_error(
                status.HTTP_400_BAD_REQUEST,
                f"单次最多上传 {config.MAX_UPLOAD_BATCH_FILES} 个文件。",
            )

        prepared_uploads = []
        total_batch_size = 0
        
        # 第一阶段: 验证所有文件
        for order, upload in enumerate(files):
            filename = str(upload.filename or "").strip() or "未命名文件"
            content_type = upload.content_type or "unknown"
            
            try:
                # 获取文件大小
                size_bytes = get_upload_size(upload)
                
                # 读取文件头部用于魔数验证
                file_obj = upload.file
                file_obj.seek(0)
                file_header = file_obj.read(16)
                file_obj.seek(0)
                
                # 完整的文件验证(扩展名、魔数、大小)
                safe_filename, extension = validate_upload_file(
                    file_header,
                    filename,
                    size_bytes,
                    skip_magic_bytes=False  # 启用魔数验证
                )
                
                total_batch_size += size_bytes
                
                prepared_uploads.append({
                    "order": order,
                    "upload": upload,
                    "filename": safe_filename,
                    "extension": extension,
                    "content_type": content_type,
                    "size_bytes": size_bytes,
                })
                
            except FileValidationError as e:
                logger.warning(f"文件验证失败: {filename}, {e.message}")
                build_error(status.HTTP_400_BAD_REQUEST, e.message)
            except Exception:
                logger.exception(f"读取文件失败: {filename}")
                build_error(status.HTTP_400_BAD_REQUEST, f"读取文件失败: {filename}")

        # 验证总大小
        if total_batch_size > config.MAX_UPLOAD_BATCH_SIZE_BYTES:
            build_error(
                status.HTTP_400_BAD_REQUEST,
                f"单次上传总大小不能超过 {config.MAX_UPLOAD_BATCH_SIZE_MB} MB。",
            )

        # 第二阶段: 准备上传任务
        upload_tasks = []
        file_data_list = []

        try:
            for item in prepared_uploads:
                if item["size_bytes"] <= 0:
                    upload_tasks.append({
                        "task_id": str(uuid.uuid4()),
                        "filename": item["filename"],
                        "size": item["size_bytes"],
                        "status": "error",
                        "message": "空文件无法导入知识库。",
                    })
                    continue

                if item["size_bytes"] > config.MAX_UPLOAD_FILE_SIZE_BYTES:
                    upload_tasks.append({
                        "task_id": str(uuid.uuid4()),
                        "filename": item["filename"],
                        "size": item["size_bytes"],
                        "status": "error",
                        "message": f"单个文件不能超过 {config.MAX_UPLOAD_FILE_SIZE_MB} MB。",
                    })
                    continue

                # 流式读取文件内容并计算SHA256
                file_obj = item["upload"].file
                file_obj.seek(0)
                
                sha256_obj = hashlib.sha256()
                file_chunks = []
                
                while chunk := file_obj.read(config.UPLOAD_STREAM_CHUNK_SIZE):
                    sha256_obj.update(chunk)
                    file_chunks.append(chunk)
                
                content_sha256 = sha256_obj.hexdigest()
                file_content = b''.join(file_chunks)

                # 检查是否重复
                registry = workspace_service.reserve_upload_registry(
                    database=database,
                    uploader=user,
                    filename=item["filename"],
                    content_type=item["content_type"],
                    size_bytes=item["size_bytes"],
                    content_sha256=content_sha256,
                )

                if registry is None:
                    # 重复文件,也需要生成task_id用于WebSocket推送
                    task_id = str(uuid.uuid4())
                    upload_tasks.append({
                        "task_id": task_id,
                        "filename": item["filename"],
                        "size": item["size_bytes"],
                        "status": "duplicate",  # 使用duplicate状态
                        "message": DUPLICATE_MESSAGE,
                    })
                    # 重复文件也要加入file_data_list,通过WebSocket推送完成消息
                    file_data_list.append({
                        "task_id": task_id,
                        "user_id": user.id,
                        "filename": item["filename"],
                        "content_type": item["content_type"],
                        "size_bytes": item["size_bytes"],
                        "content_sha256": content_sha256,
                        "registry_id": None,  # 重复文件没有registry
                        "file_content": None,  # 不需要文件内容
                        "uploader_name": user.name,
                        "is_duplicate": True,  # 标记为重复
                    })
                    continue

                task_id = str(uuid.uuid4())
                upload_tasks.append({
                    "task_id": task_id,
                    "filename": item["filename"],
                    "size": item["size_bytes"],
                    "status": "processing",
                    "message": "正在处理...",
                })

                file_data_list.append({
                    "task_id": task_id,
                    "user_id": user.id,
                    "filename": item["filename"],
                    "content_type": item["content_type"],
                    "size_bytes": item["size_bytes"],
                    "content_sha256": content_sha256,
                    "registry_id": registry.id,
                    "file_content": file_content,
                    "uploader_name": user.name,
                    "is_duplicate": False,
                })

            # 第三阶段: 添加后台任务处理文件
            if file_data_list:
                if config.RABBITMQ_ENABLED:
                    # 使用RabbitMQ异步处理
                    try:
                        from rag_app.services.queue_service import get_queue_service
                        queue_service = get_queue_service()
                        
                        for file_data in file_data_list:
                            # 编码文件内容
                            if file_data.get("file_content"):
                                import base64
                                file_data["file_data"] = base64.b64encode(file_data["file_content"]).decode('utf-8')
                                del file_data["file_content"]
                            
                            await queue_service.publish(file_data)
                        
                        logger.info(f"已发布 {len(file_data_list)} 个上传任务到RabbitMQ")
                    except Exception as e:
                        logger.error(f"RabbitMQ发布失败,回退到同步处理: {e}")
                        background_tasks.add_task(
                            process_uploads_background,
                            file_data_list,
                            user.id,
                        )
                else:
                    # 使用BackgroundTasks处理
                    background_tasks.add_task(
                        process_uploads_background,
                        file_data_list,
                        user.id,
                    )

            return {
                "message": "文件已接收，正在后台处理。",
                "tasks": upload_tasks,
                "queue_enabled": config.RABBITMQ_ENABLED,
            }
        finally:
            for upload in files:
                await upload.close()

    _register_upload_routes(app)
    return app


def process_upload_message(message: dict):
    """处理RabbitMQ上传消息(同步包装)"""
    import base64
    
    task_id = message.get("task_id")
    user_id = message.get("user_id")
    filename = message.get("filename")
    is_duplicate = message.get("is_duplicate", False)
    
    try:
        # 重复文件直接推送完成消息
        if is_duplicate:
            asyncio.run(websocket_manager.send_upload_complete(user_id, {
                "task_id": task_id,
                "filename": filename,
                "status": "duplicate",
                "message": message.get("message", "文件已存在"),
            }))
            return
        
        # 发送处理中状态
        asyncio.run(websocket_manager.send_upload_progress(user_id, {
            "task_id": task_id,
            "filename": filename,
            "status": "processing",
            "progress": 50,
        }))
        
        # 解码文件内容
        file_data = base64.b64decode(message.get("file_data", ""))
        file_obj = io.BytesIO(file_data)
        
        # 处理文件
        db_session = SessionLocal()
        try:
            upload_result = KnowledgeBaseService(user_id, redis_service=redis_service).upload_by_file(
                file_obj,
                filename,
                content_sha256=message.get("content_sha256"),
            )
            
            status_value = "success" if upload_result.get("document_id") else "warning"
            message_text = str(upload_result.get("message", "")).strip()
            
            if status_value == "success":
                upload_record = workspace_service.complete_upload(
                    database=db_session,
                    registry_id=message.get("registry_id"),
                    vector_doc_id=upload_result.get("document_id"),
                    filename=filename,
                    content_type=message.get("content_type"),
                    size_bytes=message.get("size_bytes"),
                    content_sha256=upload_result.get("content_sha256"),
                    status=status_value,
                    message=message_text,
                    uploader=db_session.get(User, user_id),
                )
                serialized = workspace_service.serialize_upload(upload_record)
                db_session.commit()
                
                asyncio.run(websocket_manager.send_upload_complete(user_id, {
                    "task_id": task_id,
                    "filename": filename,
                    "status": "success",
                    "upload": serialized,
                }))
            else:
                workspace_service.release_upload_registry(
                    database=db_session,
                    registry_id=message.get("registry_id"),
                )
                asyncio.run(websocket_manager.send_upload_complete(user_id, {
                    "task_id": task_id,
                    "filename": filename,
                    "status": status_value,
                    "message": message_text,
                }))
        finally:
            db_session.close()
            
    except Exception as e:
        logger.exception(f"处理上传消息失败: {filename}")
        db_session = SessionLocal()
        try:
            workspace_service.release_upload_registry(
                database=db_session,
                registry_id=message.get("registry_id"),
            )
        finally:
            db_session.close()
        
        asyncio.run(websocket_manager.send_upload_complete(user_id, {
            "task_id": task_id,
            "filename": filename,
            "status": "error",
            "message": "文件解析或写入知识库失败，请稍后重试。",
        }))


async def async_process_upload_message(message: dict):
    """处理RabbitMQ上传消息(异步版本)"""
    import base64
    
    task_id = message.get("task_id")
    user_id = message.get("user_id")
    filename = message.get("filename")
    is_duplicate = message.get("is_duplicate", False)
    
    try:
        # 重复文件直接推送完成消息
        if is_duplicate:
            await websocket_manager.send_upload_complete(user_id, {
                "task_id": task_id,
                "filename": filename,
                "status": "duplicate",
                "message": message.get("message", "文件已存在"),
            })
            return
        
        # 发送处理中状态
        await websocket_manager.send_upload_progress(user_id, {
            "task_id": task_id,
            "filename": filename,
            "status": "processing",
            "progress": 50,
        })
        
        # 解码文件内容
        file_data = base64.b64decode(message.get("file_data", ""))
        file_obj = io.BytesIO(file_data)
        
        # 处理文件(在线程池中执行同步操作)
        db_session = SessionLocal()
        try:
            loop = asyncio.get_event_loop()
            upload_result = await loop.run_in_executor(
                None,
                lambda: KnowledgeBaseService(user_id, redis_service=redis_service).upload_by_file(
                    file_obj,
                    filename,
                    content_sha256=message.get("content_sha256"),
                )
            )
            
            status_value = "success" if upload_result.get("document_id") else "warning"
            message_text = str(upload_result.get("message", "")).strip()
            
            if status_value == "success":
                upload_record = workspace_service.complete_upload(
                    database=db_session,
                    registry_id=message.get("registry_id"),
                    vector_doc_id=upload_result.get("document_id"),
                    filename=filename,
                    content_type=message.get("content_type"),
                    size_bytes=message.get("size_bytes"),
                    content_sha256=upload_result.get("content_sha256"),
                    status=status_value,
                    message=message_text,
                    uploader=db_session.get(User, user_id),
                )
                serialized = workspace_service.serialize_upload(upload_record)
                db_session.commit()
                
                await websocket_manager.send_upload_complete(user_id, {
                    "task_id": task_id,
                    "filename": filename,
                    "status": "success",
                    "upload": serialized,
                })
            else:
                workspace_service.release_upload_registry(
                    database=db_session,
                    registry_id=message.get("registry_id"),
                )
                await websocket_manager.send_upload_complete(user_id, {
                    "task_id": task_id,
                    "filename": filename,
                    "status": status_value,
                    "message": message_text,
                })
        finally:
            db_session.close()
            
    except Exception as e:
        logger.exception(f"处理上传消息失败: {filename}")
        db_session = SessionLocal()
        try:
            workspace_service.release_upload_registry(
                database=db_session,
                registry_id=message.get("registry_id"),
            )
        finally:
            db_session.close()
        
        await websocket_manager.send_upload_complete(user_id, {
            "task_id": task_id,
            "filename": filename,
            "status": "error",
            "message": "文件解析或写入知识库失败，请稍后重试。",
        })


def process_uploads_background(file_data_list: list[dict], user_id: str):
    """后台处理上传文件"""
    import asyncio

    db_session = SessionLocal()
    try:
        for file_data in file_data_list:
            task_id = file_data["task_id"]
            filename = file_data["filename"]

            try:
                # 检查是否是重复文件
                if file_data.get("is_duplicate"):
                    # 重复文件,直接推送完成消息
                    asyncio.run(websocket_manager.send_upload_complete(user_id, {
                        "task_id": task_id,
                        "filename": filename,
                        "status": "duplicate",
                        "message": file_data.get("message", "文件已存在"),
                    }))
                    continue

                # 发送处理中状态
                asyncio.run(websocket_manager.send_upload_progress(user_id, {
                    "task_id": task_id,
                    "filename": filename,
                    "status": "processing",
                    "progress": 50,
                }))

                # 处理文件
                file_obj = io.BytesIO(file_data["file_content"])
                upload_result = KnowledgeBaseService(user_id, redis_service=redis_service).upload_by_file(
                    file_obj,
                    filename,
                    content_sha256=file_data["content_sha256"],
                )

                message = str(upload_result.get("message", "")).strip()
                if upload_result.get("duplicate"):
                    status_value = "duplicate"  # 使用duplicate状态,前端会显示"已存在"
                elif upload_result.get("document_id"):
                    status_value = "success"
                else:
                    status_value = "warning"

                if status_value == "success":
                    try:
                        upload_record = workspace_service.complete_upload(
                            database=db_session,
                            registry_id=file_data["registry_id"],
                            vector_doc_id=upload_result.get("document_id"),
                            filename=filename,
                            content_type=file_data["content_type"],
                            size_bytes=file_data["size_bytes"],
                            content_sha256=upload_result.get("content_sha256"),
                            status=status_value,
                            message=message,
                            uploader=db_session.get(User, user_id),
                        )
                        serialized = workspace_service.serialize_upload(upload_record)
                        db_session.commit()

                        # 发送完成状态
                        asyncio.run(websocket_manager.send_upload_complete(user_id, {
                            "task_id": task_id,
                            "filename": filename,
                            "status": "success",
                            "upload": serialized,
                        }))
                        continue
                    except Exception:
                        logger.exception("Failed to persist upload record.")
                        try:
                            KnowledgeBaseService(user_id, redis_service=redis_service).delete_document(
                                document_id=upload_result.get("document_id")
                            )
                        except Exception:
                            logger.exception("Failed to roll back vector document.")
                        workspace_service.release_upload_registry(
                            database=db_session,
                            registry_id=file_data["registry_id"],
                        )
                        status_value = "error"
                        message = "写入上传记录失败，请稍后重试。"
                else:
                    workspace_service.release_upload_registry(
                        database=db_session,
                        registry_id=file_data["registry_id"],
                    )

                # 发送错误或警告状态
                asyncio.run(websocket_manager.send_upload_complete(user_id, {
                    "task_id": task_id,
                    "filename": filename,
                    "status": status_value,
                    "message": message,
                }))

            except Exception:
                logger.exception("Failed to process upload: %s", filename)
                workspace_service.release_upload_registry(
                    database=db_session,
                    registry_id=file_data["registry_id"],
                )
                asyncio.run(websocket_manager.send_upload_complete(user_id, {
                    "task_id": task_id,
                    "filename": filename,
                    "status": "error",
                    "message": "文件解析或写入知识库失败，请稍后重试。",
                }))
    finally:
        db_session.close()


def _register_upload_routes(app: FastAPI):
    @app.delete("/api/uploads/{upload_id}")
    def delete_upload(
        upload_id: str,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        try:
            upload = workspace_service.require_upload(database, user, upload_id)
        except ValueError as exc:
            build_error(status.HTTP_404_NOT_FOUND, str(exc))

        try:
            delete_result = delete_upload_entry(database, user, upload)
        except Exception:
            logger.exception("Failed to delete uploaded document.")
            build_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "删除知识库文件失败，请稍后重试。")

        return {
            "message": delete_result["message"],
            "deleted_chunks": delete_result["deleted_chunks"],
            "uploads": workspace_service.list_uploads(database, user),
        }

    @app.post("/api/uploads/batch-delete")
    def batch_delete_uploads(
        payload: BatchDeleteUploadsRequest,
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        upload_ids = payload.upload_ids

        uploads = workspace_service.list_upload_entities(database, user, upload_ids)
        upload_map = {upload.id: upload for upload in uploads}

        deleted_items = []
        failed_items = []
        for upload_id in upload_ids:
            upload = upload_map.get(upload_id)
            if upload is None:
                failed_items.append({
                    "id": upload_id,
                    "message": "文件不存在，或不属于当前账号。",
                })
                continue

            try:
                delete_result = delete_upload_entry(database, user, upload)
                deleted_items.append({
                    "id": upload.id,
                    "name": upload.filename,
                    "deleted_chunks": delete_result["deleted_chunks"],
                })
            except Exception:
                logger.exception("Failed to delete uploaded document in batch.")
                failed_items.append({
                    "id": upload.id,
                    "name": upload.filename,
                    "message": "删除失败，请稍后重试。",
                })

        summary_message = (
            f"已删除 {len(deleted_items)} 个文件"
            if not failed_items
            else f"已删除 {len(deleted_items)} 个文件，{len(failed_items)} 个删除失败"
        )

        return {
            "message": summary_message,
            "deleted": deleted_items,
            "failed": failed_items,
            "uploads": workspace_service.list_uploads(database, user),
        }


app = create_app()
