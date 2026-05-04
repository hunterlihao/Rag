import hashlib
import json
import logging
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from threading import Event, Lock

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator
from sqlalchemy.orm import Session

from rag_app import config
from rag_app.services.auth_service import AuthService
from rag_app.services.knowledge_base import DUPLICATE_MESSAGE, KnowledgeBaseService
from rag_app.services.rag_service import RagService
from rag_app.services.redis_service import RedisService
from rag_app.services.user_service import UserService
from rag_app.services.workspace_service import WorkspaceService
from rag_app.storage.database import SessionLocal, get_db, init_database
from rag_app.utils.logging_config import get_request_id, reset_log_context, set_log_context

redis_service = RedisService()
auth_service = AuthService(redis_service=redis_service)
workspace_service = WorkspaceService(redis_service=redis_service)
user_service = UserService(auth_service=auth_service)
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
        build_error(status.HTTP_401_UNAUTHORIZED, "登录状态已过期，请重新登录。")
    return user


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
    app.state.rag_service = RagService()
    logger.info("Application startup completed.", extra={"event": "app.startup.completed"})
    try:
        yield
    finally:
        logger.info("Application shutdown completed.", extra={"event": "app.shutdown.completed"})


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.API_CORS_ORIGINS,
        allow_origin_regex=config.API_CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    def delete_upload_entry(database: Session, user, upload):
        kb_service = KnowledgeBaseService(user.id)
        delete_result = kb_service.delete_document(document_id=upload.vector_doc_id)
        workspace_service.delete_upload_with_registry(database, upload)
        return delete_result

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
            assistant_reply = app.state.rag_service.invoke(
                {
                    "input": prompt,
                    "user_id": user.id,
                    "answer_mode": payload.answer_mode,
                    "chat_model_id": payload.chat_model_id,
                },
                {"configurable": {"session_id": session_id}},
            )
            workspace_service.touch_session(database, session, prompt, assistant_reply)
            return {"session": workspace_service.get_session_detail(database, user, session_id)}
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

            def persist_answer():
                nonlocal persisted
                if persisted:
                    return
                assistant_reply = "".join(assistant_parts)
                if cancel_event.is_set() and not assistant_reply.strip():
                    assistant_reply = "已停止回答。"
                app.state.rag_service.append_history(session_id, prompt, assistant_reply)
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
    def list_uploads(user=Depends(get_current_user), database: Session = Depends(get_db)):
        return {"uploads": workspace_service.list_uploads(database, user)}

    @app.post("/api/uploads")
    async def upload_files(
        files: list[UploadFile] = File(...),
        user=Depends(get_current_user),
        database: Session = Depends(get_db),
    ):
        if len(files) > config.MAX_UPLOAD_BATCH_FILES:
            build_error(
                status.HTTP_400_BAD_REQUEST,
                f"单次最多上传 {config.MAX_UPLOAD_BATCH_FILES} 个文件。",
            )

        prepared_uploads = []
        total_batch_size = 0
        for order, upload in enumerate(files):
            filename = str(upload.filename or "").strip() or "未命名文件"
            content_type = upload.content_type or "unknown"
            try:
                size_bytes = get_upload_size(upload)
            except Exception:
                logger.exception("Failed to read upload size.")
                build_error(status.HTTP_400_BAD_REQUEST, f"读取文件大小失败：{filename}，请重新选择文件。")

            total_batch_size += size_bytes
            prepared_uploads.append({
                "order": order,
                "upload": upload,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": size_bytes,
            })

        if total_batch_size > config.MAX_UPLOAD_BATCH_SIZE_BYTES:
            build_error(
                status.HTTP_400_BAD_REQUEST,
                f"单次上传总大小不能超过 {config.MAX_UPLOAD_BATCH_SIZE_MB} MB。",
            )

        upload_payloads = []
        results = []
        try:
            for item in prepared_uploads:
                if item["size_bytes"] <= 0:
                    results.append(
                        build_upload_result_payload(
                            order=item["order"],
                            filename=item["filename"],
                            content_type=item["content_type"],
                            size_bytes=item["size_bytes"],
                            status_value="error",
                            message="空文件无法导入知识库。",
                            uploader_name=user.name,
                        )
                    )
                    continue

                if item["size_bytes"] > config.MAX_UPLOAD_FILE_SIZE_BYTES:
                    results.append(
                        build_upload_result_payload(
                            order=item["order"],
                            filename=item["filename"],
                            content_type=item["content_type"],
                            size_bytes=item["size_bytes"],
                            status_value="error",
                            message=(
                                f"单个文件不能超过 {config.MAX_UPLOAD_FILE_SIZE_MB} MB，"
                                f"当前文件为 {item['filename']}。"
                            ),
                            uploader_name=user.name,
                        )
                    )
                    continue

                try:
                    content_sha256 = calculate_upload_sha256(item["upload"])
                except Exception:
                    logger.exception("Failed to calculate upload fingerprint.")
                    results.append(
                        build_upload_result_payload(
                            order=item["order"],
                            filename=item["filename"],
                            content_type=item["content_type"],
                            size_bytes=item["size_bytes"],
                            status_value="error",
                            message="计算文件指纹失败，请稍后重试。",
                            uploader_name=user.name,
                        )
                    )
                    continue

                registry = workspace_service.reserve_upload_registry(
                    database=database,
                    uploader=user,
                    filename=item["filename"],
                    content_type=item["content_type"],
                    size_bytes=item["size_bytes"],
                    content_sha256=content_sha256,
                )
                if registry is None:
                    results.append(
                        build_upload_result_payload(
                            order=item["order"],
                            filename=item["filename"],
                            content_type=item["content_type"],
                            size_bytes=item["size_bytes"],
                            status_value="warning",
                            message=DUPLICATE_MESSAGE,
                            uploader_name=user.name,
                            duplicate=True,
                        )
                    )
                    continue

                upload_payloads.append({
                    **item,
                    "registry_id": registry.id,
                    "content_sha256": content_sha256,
                })

            def process_upload(prepared_item: dict[str, object]) -> dict:
                try:
                    upload_result = KnowledgeBaseService(user.id).upload_by_file(
                        prepared_item["upload"].file,
                        prepared_item["filename"],
                        content_sha256=prepared_item["content_sha256"],
                    )
                    message = str(upload_result.get("message", "")).strip()
                    if upload_result.get("duplicate"):
                        status_value = "warning"
                    elif upload_result.get("document_id"):
                        status_value = "success"
                    else:
                        status_value = "warning"
                except ValueError as exc:
                    upload_result = {
                        "message": str(exc),
                        "duplicate": False,
                        "content_sha256": prepared_item["content_sha256"],
                        "document_id": None,
                    }
                    message = str(exc)
                    status_value = "error"
                except Exception:
                    logger.exception("Failed to process upload: %s", prepared_item["filename"])
                    upload_result = {
                        "message": "文件解析或写入知识库失败，请稍后重试。",
                        "duplicate": False,
                        "content_sha256": prepared_item["content_sha256"],
                        "document_id": None,
                    }
                    message = "文件解析或写入知识库失败，请稍后重试。"
                    status_value = "error"

                return {
                    "order": prepared_item["order"],
                    "registry_id": prepared_item["registry_id"],
                    "content_sha256": prepared_item["content_sha256"],
                    "filename": prepared_item["filename"],
                    "content_type": prepared_item["content_type"],
                    "size_bytes": prepared_item["size_bytes"],
                    "status": status_value,
                    "message": message,
                    "upload_result": upload_result,
                }

            if len(upload_payloads) <= 1:
                processed_payloads = [process_upload(payload) for payload in upload_payloads]
            else:
                max_workers = max(1, min(config.UPLOAD_MAX_WORKERS, len(upload_payloads)))
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    processed_payloads = list(executor.map(process_upload, upload_payloads))

            for processed in processed_payloads:
                status_value = processed["status"]
                message = processed["message"]
                upload_result = processed["upload_result"]
                if status_value == "success":
                    try:
                        upload_record = workspace_service.complete_upload(
                            database=database,
                            registry_id=processed["registry_id"],
                            vector_doc_id=upload_result.get("document_id"),
                            filename=processed["filename"],
                            content_type=processed["content_type"],
                            size_bytes=processed["size_bytes"],
                            content_sha256=upload_result.get("content_sha256"),
                            status=status_value,
                            message=message,
                            uploader=user,
                        )
                        serialized_upload = workspace_service.serialize_upload(upload_record)
                        serialized_upload["order"] = processed["order"]
                        results.append(serialized_upload)
                        continue
                    except Exception:
                        logger.exception("Failed to persist upload record.")
                        try:
                            KnowledgeBaseService(user.id).delete_document(
                                document_id=upload_result.get("document_id")
                            )
                        except Exception:
                            logger.exception("Failed to roll back vector document.")

                        workspace_service.release_upload_registry(
                            database=database,
                            registry_id=processed["registry_id"],
                        )
                        status_value = "error"
                        message = "写入上传记录失败，请稍后重试。"
                else:
                    workspace_service.release_upload_registry(
                        database=database,
                        registry_id=processed["registry_id"],
                    )

                results.append(
                    build_upload_result_payload(
                        order=processed["order"],
                        filename=processed["filename"],
                        content_type=processed["content_type"],
                        size_bytes=processed["size_bytes"],
                        status_value=status_value,
                        message=message,
                        uploader_name=user.name,
                        duplicate=bool(upload_result.get("duplicate")) or message == DUPLICATE_MESSAGE,
                    )
                )

            results.sort(key=lambda item: item.get("order", 0))
            for result in results:
                result.pop("order", None)

            return {
                "results": results,
                "uploads": workspace_service.list_uploads(database, user),
            }
        finally:
            for upload in files:
                await upload.close()

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

    return app


app = create_app()
