import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from langchain_community.llms.tongyi import Tongyi
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_text_splitters import RecursiveCharacterTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)


def env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_identifier(key: str, default: str) -> str:
    value = (os.getenv(key, default) or default).strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise RuntimeError(f"{key} 只能包含字母、数字和下划线，且不能以数字开头。")
    return value


def split_env_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]

APP_NAME = os.getenv("RAG_APP_NAME", "rag-api").strip() or "rag-api"
APP_ENV = os.getenv("RAG_APP_ENV", "local").strip() or "local"
LOG_LEVEL = os.getenv("RAG_LOG_LEVEL", "INFO").strip().upper() or "INFO"
LOG_FORMAT = os.getenv("RAG_LOG_FORMAT", "spring").strip().lower() or "spring"
LOG_CONSOLE_FORMAT = os.getenv("RAG_LOG_CONSOLE_FORMAT", "spring").strip().lower() or "spring"
LOG_COLOR_ENABLED = env_bool("RAG_LOG_COLOR_ENABLED", True)
LOG_TO_FILE = env_bool("RAG_LOG_TO_FILE", False)
LOG_DIR = os.getenv("RAG_LOG_DIR", str(PROJECT_ROOT / "logs")).strip()
LOG_FILE_NAME = os.getenv("RAG_LOG_FILE_NAME", "rag-api.log").strip() or "rag-api.log"
LOG_MAX_BYTES = int(os.getenv("RAG_LOG_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("RAG_LOG_BACKUP_COUNT", "10"))
LOG_ACCESS_ENABLED = env_bool("RAG_LOG_ACCESS_ENABLED", False)
LOG_SLOW_REQUEST_MS = int(os.getenv("RAG_LOG_SLOW_REQUEST_MS", "2000"))

COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "rag_cosine")
VECTOR_DISTANCE_SPACE = os.getenv("RAG_VECTOR_DISTANCE_SPACE", "cosine")
COLLECTION_METADATA = {"hnsw:space": VECTOR_DISTANCE_SPACE}
PERSIST_DIRECTORY = str(PROJECT_ROOT / "chroma_db")
CHROMA_MODE = os.getenv("RAG_CHROMA_MODE", "local").strip().lower()
CHROMA_HOST = os.getenv("RAG_CHROMA_HOST", "127.0.0.1").strip()
CHROMA_PORT = int(os.getenv("RAG_CHROMA_PORT", "8001"))
CHROMA_SSL = env_bool("RAG_CHROMA_SSL", False)

POSTGRES_HOST = os.getenv("RAG_POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("RAG_POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("RAG_POSTGRES_DB", "postgres")
POSTGRES_USER = os.getenv("RAG_POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("RAG_POSTGRES_PASSWORD", "root")
CHAT_HISTORY_TABLE_NAME = env_identifier("RAG_HISTORY_TABLE", "rag_chat_history")
POSTGRES_CONNECTION_URL = (
    f"postgresql+psycopg2://{quote_plus(POSTGRES_USER)}:{quote_plus(POSTGRES_PASSWORD)}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{quote_plus(POSTGRES_DB)}"
)
POSTGRES_ENGINE_ARGS = {
    "pool_pre_ping": True,
    "connect_args": {"sslmode": "disable"},
}

SUPPORTED_UPLOAD_EXTENSIONS = ["txt", "md", "pdf", "docx", "xlsx", "xls", "csv"]

OLLAMA_EMBEDDING_FUNCTION = OllamaEmbeddings(
    model=os.getenv("RAG_EMBEDDING_MODEL", "qwen3-embedding:latest"),
    base_url=os.getenv("RAG_OLLAMA_BASE_URL", "http://localhost:11434"),
)
TEXT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "500")),
    chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "100")),
    separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],
    length_function=len,
)
MAX_SPLIT_CHAR_NUM = int(os.getenv("RAG_MAX_SPLIT_CHAR_NUM", "500"))

RETRIEVAL_TOP_K = int(os.getenv("RAG_RETRIEVAL_TOP_K", os.getenv("RAG_SIMILARITY_TOP_K", "5")))
RETRIEVAL_FETCH_K = int(os.getenv("RAG_RETRIEVAL_FETCH_K", "20"))

SIMILARITY_THRESHOLD_ENABLED = env_bool("RAG_SIMILARITY_THRESHOLD_ENABLED", True)
SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.35"))

MMR_ENABLED = env_bool("RAG_MMR_ENABLED", True)
MMR_LAMBDA_MULT = float(os.getenv("RAG_MMR_LAMBDA_MULT", "0.6"))
MMR_CANDIDATE_K = int(os.getenv("RAG_MMR_CANDIDATE_K", "8"))

QUERY_REWRITE_ENABLED = env_bool("RAG_QUERY_REWRITE_ENABLED", True)
QUERY_REWRITE_HISTORY_TURNS = int(os.getenv("RAG_QUERY_REWRITE_HISTORY_TURNS", "3"))

RERANK_ENABLED = env_bool("RAG_RERANK_ENABLED", True)
RERANK_TOP_K = int(os.getenv("RAG_RERANK_TOP_K", str(RETRIEVAL_TOP_K)))
DEBUG_RETRIEVAL = env_bool("RAG_DEBUG_RETRIEVAL", False)
UPLOAD_MAX_WORKERS = int(os.getenv("RAG_UPLOAD_MAX_WORKERS", "4"))
MAX_UPLOAD_FILE_SIZE_MB = int(os.getenv("RAG_MAX_UPLOAD_FILE_SIZE_MB", "20"))
MAX_UPLOAD_BATCH_SIZE_MB = int(os.getenv("RAG_MAX_UPLOAD_BATCH_SIZE_MB", "60"))
MAX_UPLOAD_BATCH_FILES = int(os.getenv("RAG_MAX_UPLOAD_BATCH_FILES", "10"))
UPLOAD_STREAM_CHUNK_SIZE = int(os.getenv("RAG_UPLOAD_STREAM_CHUNK_SIZE", str(1024 * 1024)))
MAX_UPLOAD_FILE_SIZE_BYTES = MAX_UPLOAD_FILE_SIZE_MB * 1024 * 1024
MAX_UPLOAD_BATCH_SIZE_BYTES = MAX_UPLOAD_BATCH_SIZE_MB * 1024 * 1024
MAX_PROMPT_CHARS = int(os.getenv("RAG_MAX_PROMPT_CHARS", "8000"))
MAX_BATCH_DELETE_UPLOADS = int(os.getenv("RAG_MAX_BATCH_DELETE_UPLOADS", "100"))
ANSWER_MODE_AUTO = "auto"
ANSWER_MODE_KNOWLEDGE = "knowledge"
ANSWER_MODE_CHAT = "chat"
SUPPORTED_ANSWER_MODES = {
    ANSWER_MODE_AUTO,
    ANSWER_MODE_KNOWLEDGE,
    ANSWER_MODE_CHAT,
}

LOCAL_CHAT_MODEL_NAME = os.getenv("RAG_LOCAL_MODEL", "qwen3.5:9b")
REMOTE_CHAT_MODEL_NAME = os.getenv("RAG_CHAT_MODEL", "qwen-max")
EMBEDDING_MODEL_NAME = os.getenv("RAG_EMBEDDING_MODEL", "qwen3-embedding:latest")
OLLAMA_BASE_URL = os.getenv("RAG_OLLAMA_BASE_URL", "http://localhost:11434")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")

REDIS_URL = os.getenv("RAG_REDIS_URL", "redis://127.0.0.1:6379/0").strip()
REDIS_KEY_PREFIX = os.getenv("RAG_REDIS_KEY_PREFIX", "rag").strip() or "rag"
TRUST_PROXY_HEADERS = env_bool("RAG_TRUST_PROXY_HEADERS", False)
TRUSTED_PROXY_IPS = {
    item.strip()
    for item in os.getenv("RAG_TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
    if item.strip()
}
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("RAG_LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300")
)
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = int(
    os.getenv("RAG_LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5")
)
REGISTER_RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("RAG_REGISTER_RATE_LIMIT_WINDOW_SECONDS", "1800")
)
REGISTER_RATE_LIMIT_MAX_ATTEMPTS = int(
    os.getenv("RAG_REGISTER_RATE_LIMIT_MAX_ATTEMPTS", "5")
)
SESSION_CACHE_TTL_SECONDS = int(os.getenv("RAG_SESSION_CACHE_TTL_SECONDS", "180"))
UPLOAD_REGISTRY_STALE_SECONDS = int(
    os.getenv("RAG_UPLOAD_REGISTRY_STALE_SECONDS", "1800")
)

USE_LOCAL_CHAT_MODEL = env_bool("RAG_USE_LOCAL_CHAT_MODEL", False)
CHAT_MODEL_PROVIDER_OLLAMA = "ollama"
CHAT_MODEL_PROVIDER_TONGYI = "tongyi"
SUPPORTED_CHAT_MODEL_PROVIDERS = {
    CHAT_MODEL_PROVIDER_OLLAMA,
    CHAT_MODEL_PROVIDER_TONGYI,
}


def build_chat_model_id(provider: str, model_name: str) -> str:
    return f"{provider}:{model_name.strip()}"


def build_chat_model_label(provider: str, model_name: str) -> str:
    provider_label = "Ollama" if provider == CHAT_MODEL_PROVIDER_OLLAMA else "通义千问"
    return f"{provider_label} {model_name}"


def parse_chat_model_option(raw_option: str) -> dict | None:
    option_parts = [part.strip() for part in raw_option.split("|")]
    model_id = option_parts[0] if option_parts else ""
    label = option_parts[1] if len(option_parts) > 1 else ""

    if ":" not in model_id:
        return None

    provider, model_name = model_id.split(":", 1)
    provider = provider.strip().lower()
    model_name = model_name.strip()
    if provider not in SUPPORTED_CHAT_MODEL_PROVIDERS or not model_name:
        return None

    provider_label = "Ollama 本地模型" if provider == CHAT_MODEL_PROVIDER_OLLAMA else "通义千问"
    return {
        "id": build_chat_model_id(provider, model_name),
        "provider": provider,
        "provider_label": provider_label,
        "model": model_name,
        "label": label or build_chat_model_label(provider, model_name),
    }


def build_chat_model_options() -> list[dict]:
    raw_options = split_env_list(os.getenv("RAG_CHAT_MODEL_OPTIONS", ""))
    parsed_options = [parse_chat_model_option(item) for item in raw_options]
    model_options = [item for item in parsed_options if item is not None]

    if not model_options:
        default_ids = [
            build_chat_model_id(CHAT_MODEL_PROVIDER_TONGYI, REMOTE_CHAT_MODEL_NAME),
            build_chat_model_id(CHAT_MODEL_PROVIDER_OLLAMA, LOCAL_CHAT_MODEL_NAME),
        ]
        if USE_LOCAL_CHAT_MODEL:
            default_ids.reverse()
        model_options = [
            option
            for option in (parse_chat_model_option(item) for item in default_ids)
            if option is not None
        ]

    deduped_options = []
    seen_ids = set()
    for option in model_options:
        if option["id"] in seen_ids:
            continue
        seen_ids.add(option["id"])
        deduped_options.append(option)
    return deduped_options


CHAT_MODEL_OPTIONS = build_chat_model_options()
CHAT_MODEL_OPTION_BY_ID = {option["id"]: option for option in CHAT_MODEL_OPTIONS}
DEFAULT_CHAT_MODEL_ID = (
    build_chat_model_id(CHAT_MODEL_PROVIDER_OLLAMA, LOCAL_CHAT_MODEL_NAME)
    if USE_LOCAL_CHAT_MODEL
    else build_chat_model_id(CHAT_MODEL_PROVIDER_TONGYI, REMOTE_CHAT_MODEL_NAME)
)
if DEFAULT_CHAT_MODEL_ID not in CHAT_MODEL_OPTION_BY_ID and CHAT_MODEL_OPTIONS:
    DEFAULT_CHAT_MODEL_ID = CHAT_MODEL_OPTIONS[0]["id"]


def normalize_chat_model_id(model_id: str | None) -> str:
    candidate_id = str(model_id or DEFAULT_CHAT_MODEL_ID).strip()
    if candidate_id in CHAT_MODEL_OPTION_BY_ID:
        return candidate_id
    return DEFAULT_CHAT_MODEL_ID


def get_chat_model_option(model_id: str | None = None) -> dict:
    normalized_model_id = normalize_chat_model_id(model_id)
    return CHAT_MODEL_OPTION_BY_ID[normalized_model_id]


@lru_cache(maxsize=16)
def get_chat_model(model_id: str | None = None):
    option = get_chat_model_option(model_id)
    if option["provider"] == CHAT_MODEL_PROVIDER_OLLAMA:
        return OllamaLLM(
            model=option["model"],
            base_url=OLLAMA_BASE_URL,
        )
    return Tongyi(
        api_key=DASHSCOPE_API_KEY,
        model=option["model"],
    )


DEFAULT_CHAT_MODEL_OPTION = get_chat_model_option(DEFAULT_CHAT_MODEL_ID)
ACTIVE_CHAT_MODEL_NAME = DEFAULT_CHAT_MODEL_OPTION["model"]
ACTIVE_CHAT_MODEL_PROVIDER = DEFAULT_CHAT_MODEL_OPTION["provider_label"]

DEFAULT_SESSION_CONFIG = {
    "configurable": {
        "session_id": os.getenv("RAG_SESSION_ID", "hunter1"),
    }
}

API_SECRET_KEY = os.getenv("RAG_API_SECRET_KEY", "").strip()
API_JWT_ALGORITHM = os.getenv("RAG_API_JWT_ALGORITHM", "HS256")
API_JWT_ISSUER = os.getenv("RAG_API_JWT_ISSUER", "rag-api").strip() or "rag-api"
API_JWT_AUDIENCE = os.getenv("RAG_API_JWT_AUDIENCE", "rag-frontend").strip() or "rag-frontend"
API_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("RAG_API_ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
ADMIN_BOOTSTRAP_NAME = os.getenv("RAG_ADMIN_NAME", "系统管理员").strip() or "系统管理员"
ADMIN_BOOTSTRAP_EMAIL = os.getenv("RAG_ADMIN_EMAIL", "").strip().lower()
ADMIN_BOOTSTRAP_PASSWORD = os.getenv("RAG_ADMIN_PASSWORD", "").strip()
API_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "RAG_API_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
]
API_CORS_ORIGIN_REGEX = os.getenv("RAG_API_CORS_ORIGIN_REGEX", "").strip() or None


def sanitize_user_key(user_id: str | None) -> str:
    if not user_id:
        return "default"

    normalized = "".join(character for character in user_id.lower() if character.isalnum())
    return (normalized or "default")[:24]


def build_user_collection_name(user_id: str | None) -> str:
    if not user_id:
        return COLLECTION_NAME

    suffix = sanitize_user_key(user_id)
    collection_name = f"{COLLECTION_NAME}_{suffix}"[:63]
    return collection_name.rstrip("_-")


def build_chroma_kwargs(collection_name: str, embedding_function):
    common_kwargs = {
        "collection_name": collection_name,
        "embedding_function": embedding_function,
        "collection_metadata": COLLECTION_METADATA,
    }

    if CHROMA_MODE == "http":
        return {
            **common_kwargs,
            "host": CHROMA_HOST,
            "port": CHROMA_PORT,
            "ssl": CHROMA_SSL,
        }

    os.makedirs(PERSIST_DIRECTORY, exist_ok=True)
    return {
        **common_kwargs,
        "persist_directory": PERSIST_DIRECTORY,
    }


def validate_server_config():
    if not API_SECRET_KEY:
        raise RuntimeError("请在 .env 中配置 RAG_API_SECRET_KEY,不能为空。")

    if API_SECRET_KEY == "rag-dev-secret-change-me":
        raise RuntimeError("请把 RAG_API_SECRET_KEY 改成随机密钥后再启动服务。")
    
    # 安全漏洞修复9: 验证JWT密钥强度
    if len(API_SECRET_KEY) < 32:
        raise RuntimeError(
            "RAG_API_SECRET_KEY 长度至少为32字符,建议使用更强的随机密钥。\n"
            "生成方法: python -c 'import secrets; print(secrets.token_hex(32))'"
        )

    if not ADMIN_BOOTSTRAP_EMAIL:
        raise RuntimeError("请在 .env 中配置 RAG_ADMIN_EMAIL,用于初始化管理员账号。")

    if not ADMIN_BOOTSTRAP_PASSWORD:
        raise RuntimeError("请在 .env 中配置 RAG_ADMIN_PASSWORD,用于初始化管理员账号。")
