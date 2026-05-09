# RAG 系统配置文件详细注释版
# 本文件包含所有配置项的详细说明

import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from langchain_community.llms.tongyi import Tongyi
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 项目根目录路径（自动计算）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# .env 文件路径
ENV_FILE = PROJECT_ROOT / ".env"
# 加载 .env 文件中的环境变量
load_dotenv(ENV_FILE)


# ========================================
# 辅助函数
# ========================================

def env_bool(key: str, default: bool) -> bool:
    """
    将环境变量转换为布尔值
    支持的值: "1", "true", "yes", "on"（不区分大小写）
    """
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_identifier(key: str, default: str) -> str:
    """
    验证标识符格式（只能包含字母、数字、下划线，不能以数字开头）
    用于数据库表名等需要严格格式的场景
    """
    value = (os.getenv(key, default) or default).strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise RuntimeError(f"{key} 只能包含字母、数字和下划线，且不能以数字开头。")
    return value


def split_env_list(value: str) -> list[str]:
    """将逗号分隔的字符串转换为列表"""
    return [item.strip() for item in value.split(",") if item.strip()]


# ========================================
# 应用基础配置
# ========================================
# 应用名称，用于标识和日志输出
# 需要配置：自定义应用名称，例如 "my-rag-app"
APP_NAME = os.getenv("RAG_APP_NAME", "rag-api").strip() or "rag-api"

# 应用运行环境：local(本地开发) / dev(开发环境) / test(测试环境) / prod(生产环境)
# 需要配置：根据部署环境设置对应的值
APP_ENV = os.getenv("RAG_APP_ENV", "local").strip() or "local"


# ========================================
# 日志配置
# ========================================
# 日志级别：DEBUG / INFO / WARNING / ERROR / CRITICAL
# 需要配置：开发环境用 DEBUG，生产环境用 INFO 或 WARNING
LOG_LEVEL = os.getenv("RAG_LOG_LEVEL", "INFO").strip().upper() or "INFO"

# 日志格式：spring(Spring Boot风格) / json(JSON格式) / text(纯文本)
# 需要配置：本地开发用 spring，生产环境用 json 便于日志收集
LOG_FORMAT = os.getenv("RAG_LOG_FORMAT", "spring").strip().lower() or "spring"

# 控制台日志格式，与 LOG_FORMAT 相同选项
LOG_CONSOLE_FORMAT = os.getenv("RAG_LOG_CONSOLE_FORMAT", "spring").strip().lower() or "spring"

# 是否启用彩色日志输出（终端中显示不同颜色）
# 需要配置：本地开发建议开启，生产环境关闭
LOG_COLOR_ENABLED = env_bool("RAG_LOG_COLOR_ENABLED", True)

# 是否将日志输出到文件（False=仅控制台）
# 需要配置：生产环境建议开启
LOG_TO_FILE = env_bool("RAG_LOG_TO_FILE", False)

# 日志文件存储目录（绝对路径或相对路径）
# 需要配置：日志文件保存位置，确保目录有写入权限
LOG_DIR = os.getenv("RAG_LOG_DIR", str(PROJECT_ROOT / "logs")).strip()

# 日志文件名
# 需要配置：日志文件名称
LOG_FILE_NAME = os.getenv("RAG_LOG_FILE_NAME", "rag-api.log").strip() or "rag-api.log"

# 单个日志文件最大大小（字节），默认 10MB，超过后自动切割
# 需要配置：根据磁盘空间调整，10*1024*1024 = 10MB
LOG_MAX_BYTES = int(os.getenv("RAG_LOG_MAX_BYTES", str(10 * 1024 * 1024)))

# 保留的日志文件数量，超过后删除最旧的文件
# 需要配置：保留多少个历史日志文件
LOG_BACKUP_COUNT = int(os.getenv("RAG_LOG_BACKUP_COUNT", "10"))

# 是否启用访问日志（记录每个 HTTP 请求）
# 需要配置：生产环境建议开启用于审计
LOG_ACCESS_ENABLED = env_bool("RAG_LOG_ACCESS_ENABLED", False)

# 慢请求阈值（毫秒），超过此时长的请求会被标记为慢请求
# 需要配置：根据性能要求调整，2000ms = 2秒
LOG_SLOW_REQUEST_MS = int(os.getenv("RAG_LOG_SLOW_REQUEST_MS", "2000"))


# ========================================
# 向量数据库配置 (ChromaDB)
# ========================================
# ChromaDB 集合名称，用于隔离不同项目的向量数据
# 需要配置：不同项目使用不同名称避免冲突
COLLECTION_NAME = os.getenv("RAG_COLLECTION_NAME", "rag_cosine")

# 向量距离计算方式：cosine(余弦相似度) / l2(欧氏距离) / ip(内积)
# 需要配置：文本推荐用 cosine，图像推荐用 l2
VECTOR_DISTANCE_SPACE = os.getenv("RAG_VECTOR_DISTANCE_SPACE", "cosine")

# ChromaDB 集合元数据，指定距离空间（HNSW 算法配置）
# 说明：自动生成，无需手动配置
COLLECTION_METADATA = {"hnsw:space": VECTOR_DISTANCE_SPACE}

# 本地模式下的向量数据持久化目录（相对于项目根目录）
# 需要配置：本地存储向量数据库文件的位置
PERSIST_DIRECTORY = str(PROJECT_ROOT / "chroma_db")

# ChromaDB 运行模式：local(本地文件存储) / http(HTTP 远程服务)
# 需要配置：单机用 local，分布式部署用 http
CHROMA_MODE = os.getenv("RAG_CHROMA_MODE", "local").strip().lower()

# ChromaDB HTTP 服务地址（仅在 CHROMA_MODE=http 时使用）
# 需要配置：远程 ChromaDB 服务器的 IP 或域名
CHROMA_HOST = os.getenv("RAG_CHROMA_HOST", "127.0.0.1").strip()

# ChromaDB HTTP 服务端口（默认 8001）
# 需要配置：远程 ChromaDB 服务器的端口
CHROMA_PORT = int(os.getenv("RAG_CHROMA_PORT", "8001"))

# 是否使用 HTTPS 连接 ChromaDB（生产环境建议开启）
# 需要配置：生产环境建议设为 True
CHROMA_SSL = env_bool("RAG_CHROMA_SSL", False)


# ========================================
# PostgreSQL 数据库配置
# ========================================
# PostgreSQL 数据库服务器地址（IP 或域名）
# 需要配置：数据库服务器地址
POSTGRES_HOST = os.getenv("RAG_POSTGRES_HOST", "127.0.0.1")

# PostgreSQL 数据库端口（默认 5432）
# 需要配置：数据库端口号
POSTGRES_PORT = int(os.getenv("RAG_POSTGRES_PORT", "5432"))

# PostgreSQL 数据库名称
# 需要配置：要连接的数据库名
POSTGRES_DB = os.getenv("RAG_POSTGRES_DB", "postgres")

# PostgreSQL 数据库用户名
# 需要配置：数据库登录用户名
POSTGRES_USER = os.getenv("RAG_POSTGRES_USER", "postgres")

# PostgreSQL 数据库密码（生产环境请使用强密码）
# 需要配置：数据库登录密码
POSTGRES_PASSWORD = os.getenv("RAG_POSTGRES_PASSWORD", "root")

# 聊天记录表名（只能包含字母、数字、下划线，不能以数字开头）
# 需要配置：存储聊天记录的表名
CHAT_HISTORY_TABLE_NAME = env_identifier("RAG_HISTORY_TABLE", "rag_chat_history")

# PostgreSQL 连接字符串（自动组装，使用 URL 编码处理特殊字符）
# 说明：自动生成，无需手动配置
POSTGRES_CONNECTION_URL = (
    f"postgresql+psycopg2://{quote_plus(POSTGRES_USER)}:{quote_plus(POSTGRES_PASSWORD)}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{quote_plus(POSTGRES_DB)}"
)

# SQLAlchemy 引擎参数配置
# 说明：自动生成，无需手动配置
POSTGRES_ENGINE_ARGS = {
    "pool_pre_ping": True,  # 连接前检测连接是否有效
    "connect_args": {"sslmode": "disable"},  # 禁用 SSL（生产环境建议启用）
}


# ========================================
# 文件上传配置
# ========================================
# 支持上传的文件扩展名列表（白名单）
# 需要配置：允许上传的文件类型
SUPPORTED_UPLOAD_EXTENSIONS = ["txt", "md", "pdf", "docx", "xlsx", "xls", "csv"]

# 文件魔数验证配置 (通过文件头部的magic bytes验证真实文件类型，防止伪造扩展名)
# 说明：自动生成，无需手动配置
FILE_MAGIC_SIGNATURES = {
    "pdf": [b"%PDF-"],  # PDF文件以%PDF-开头
    "docx": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],  # DOCX是ZIP格式
    "xlsx": [b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"],  # XLSX是ZIP格式
    "xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],  # 老式Excel文件
}

# 允许文本文件的最小字节数（小于此值的文件被视为空文件）
# 需要配置：空文件检测阈值
MIN_TEXT_FILE_SIZE = 1

# WebSocket认证超时时间（秒），客户端必须在此时间内完成认证
# 需要配置：WebSocket 连接认证超时时间
WS_AUTH_TIMEOUT_SECONDS = 30


# ========================================
# Redis 缓存 TTL 配置（单位：秒）
# ========================================
# 向量检索结果缓存时间（10分钟），超时后重新检索
# 需要配置：缓存有效期，根据更新频率调整
REDIS_CACHE_TTL_VECTOR_SEARCH = 600

# 查询意图分类缓存时间（1小时），相同问题直接使用缓存结果
# 需要配置：意图缓存有效期
REDIS_CACHE_TTL_QUERY_INTENT = 3600

# 模型加载状态缓存时间（1小时），避免重复检查模型状态
# 需要配置：模型状态缓存有效期
REDIS_CACHE_TTL_MODEL_STATUS = 3600

# 用户偏好设置缓存时间（24小时），减少数据库查询
# 需要配置：用户设置缓存有效期
REDIS_CACHE_TTL_USER_PREFERENCES = 86400

# 上传文档 SHA256 去重缓存时间（7天），快速识别重复文件
# 需要配置：文件去重缓存有效期
REDIS_CACHE_TTL_UPLOAD_SHA256 = 604800

# 知识库集合元信息缓存时间（5分钟），上传/删除后自动失效
# 需要配置：知识库元数据缓存有效期
REDIS_CACHE_TTL_COLLECTION_META = 300

# 会话消息热点缓存时间（30分钟），加速频繁访问的会话
# 需要配置：热点会话缓存有效期
REDIS_CACHE_TTL_SESSION_MESSAGES = 1800


# ========================================
# RAG 检索缓存配置
# ========================================
# 检索缓存最大条目数，超过后使用 LRU 策略淘汰旧缓存
# 需要配置：根据内存大小调整
RETRIEVAL_CACHE_MAX_SIZE = 1000

# 检索缓存过期时间（5分钟），超时后重新检索
# 需要配置：检索结果缓存有效期
RETRIEVAL_CACHE_TTL_SECONDS = 300


# ========================================
# 嵌入模型和文本分割配置
# ========================================
# Ollama 嵌入模型配置（用于将文本转换为向量）
# 需要配置：模型名称和 Ollama 服务地址
OLLAMA_EMBEDDING_FUNCTION = OllamaEmbeddings(
    model=os.getenv("RAG_EMBEDDING_MODEL", "qwen3-embedding:latest"),  # 嵌入模型名称
    base_url=os.getenv("RAG_OLLAMA_BASE_URL", "http://localhost:11434"),  # Ollama 服务地址
)

# 文本分割器配置（将长文档切分为多个片段）
# 需要配置：根据文档类型和模型上下文窗口调整
TEXT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "500")),  # 每个文本块的最大字符数
    chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "100")),  # 文本块之间的重叠字符数（保持上下文连贯）
    separators=["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""],  # 分割优先级：段落 > 句子 > 词语
    length_function=len,  # 计算文本长度的函数
)

# 单个文档最大分割字符数，超过此限制的文档将被截断
# 需要配置：防止超长文档导致性能问题
MAX_SPLIT_CHAR_NUM = int(os.getenv("RAG_MAX_SPLIT_CHAR_NUM", "500"))


# ========================================
# RAG 检索策略配置
# ========================================
# 检索返回的候选文档数量（首先从数据库获取这么多文档）
# 需要配置：根据精度要求调整，值越大召回率越高
RETRIEVAL_FETCH_K = int(os.getenv("RAG_RETRIEVAL_FETCH_K", "20"))

# 最终返回给用户的 Top-K 文档数量（经过过滤和重排后的数量）
# 需要配置：发送给 LLM 的文档数量，通常 3-10
RETRIEVAL_TOP_K = int(os.getenv("RAG_RETRIEVAL_TOP_K", os.getenv("RAG_SIMILARITY_TOP_K", "5")))

# 是否启用相似度阈值过滤（低于阈值的文档将被排除）
# 需要配置：True=启用过滤，False=不启用
SIMILARITY_THRESHOLD_ENABLED = env_bool("RAG_SIMILARITY_THRESHOLD_ENABLED", True)

# 相似度阈值（0-1之间），值越小表示要求越严格（余弦距离）
# 需要配置：根据嵌入模型调整，0.35 适合大多数场景
SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.35"))

# 是否启用 MMR（最大边际相关性）算法，用于减少结果冗余度
# 需要配置：True=启用多样性，False=仅按相似度排序
MMR_ENABLED = env_bool("RAG_MMR_ENABLED", True)

# MMR 多样性权重（0-1之间），值越大多样性越强，相关性越弱
# 需要配置：0.6 表示相关性和多样性的平衡
MMR_LAMBDA_MULT = float(os.getenv("RAG_MMR_LAMBDA_MULT", "0.6"))

# MMR 候选文档数量（从这么多文档中选择 Top-K）
# 需要配置：应该大于 RETRIEVAL_TOP_K
MMR_CANDIDATE_K = int(os.getenv("RAG_MMR_CANDIDATE_K", "8"))

# 是否启用查询重写（将多轮对话历史合并为单个查询）
# 需要配置：True=启用多轮对话，False=单轮问答
QUERY_REWRITE_ENABLED = env_bool("RAG_QUERY_REWRITE_ENABLED", True)

# 查询重写时使用的历史对话轮数（包含最近几轮对话）
# 需要配置：通常 2-5 轮
QUERY_REWRITE_HISTORY_TURNS = int(os.getenv("RAG_QUERY_REWRITE_HISTORY_TURNS", "3"))

# 是否启用重排模型（对检索结果进行二次排序）
# 需要配置：True=启用重排提高精度，False=仅用向量相似度
RERANK_ENABLED = env_bool("RAG_RERANK_ENABLED", True)

# 重排后返回的文档数量（通常与 RETRIEVAL_TOP_K 相同）
# 需要配置：最终返回给用户的文档数
RERANK_TOP_K = int(os.getenv("RAG_RERANK_TOP_K", str(RETRIEVAL_TOP_K)))

# 是否启用检索调试模式（输出详细的检索过程和分数）
# 需要配置：开发调试时开启，生产环境关闭
DEBUG_RETRIEVAL = env_bool("RAG_DEBUG_RETRIEVAL", False)


# ========================================
# 文件上传限制配置
# ========================================
# 文件上传并发工作线程数（同时处理多少个上传任务）
# 需要配置：根据 CPU 核心数调整
UPLOAD_MAX_WORKERS = int(os.getenv("RAG_UPLOAD_MAX_WORKERS", "4"))

# 单个文件最大大小（MB），超过此限制的文件将被拒绝
# 需要配置：根据业务需求调整
MAX_UPLOAD_FILE_SIZE_MB = int(os.getenv("RAG_MAX_UPLOAD_FILE_SIZE_MB", "20"))

# 批量上传总大小限制（MB），一次上传的所有文件总大小不能超过此值
# 需要配置：批量上传的总大小上限
MAX_UPLOAD_BATCH_SIZE_MB = int(os.getenv("RAG_MAX_UPLOAD_BATCH_SIZE_MB", "60"))

# 批量上传最大文件数量，一次最多上传多少个文件
# 需要配置：单次上传的文件数限制
MAX_UPLOAD_BATCH_FILES = int(os.getenv("RAG_MAX_UPLOAD_BATCH_FILES", "10"))

# 流式上传分块大小（字节），用于大文件分块传输
# 需要配置：分块传输的块大小，1MB = 1024*1024
UPLOAD_STREAM_CHUNK_SIZE = int(os.getenv("RAG_UPLOAD_STREAM_CHUNK_SIZE", str(1024 * 1024)))

# 单个文件最大字节数（自动计算，不需要手动配置）
# 说明：自动生成，无需手动配置
MAX_UPLOAD_FILE_SIZE_BYTES = MAX_UPLOAD_FILE_SIZE_MB * 1024 * 1024

# 批量上传总字节数限制（自动计算，不需要手动配置）
# 说明：自动生成，无需手动配置
MAX_UPLOAD_BATCH_SIZE_BYTES = MAX_UPLOAD_BATCH_SIZE_MB * 1024 * 1024

# 发送给 LLM 的最大提示词字符数（防止上下文超长）
# 需要配置：根据模型上下文窗口调整
MAX_PROMPT_CHARS = int(os.getenv("RAG_MAX_PROMPT_CHARS", "8000"))

# 批量删除最大数量限制，一次最多删除多少个上传记录
# 需要配置：防止误操作删除太多文件
MAX_BATCH_DELETE_UPLOADS = int(os.getenv("RAG_MAX_BATCH_DELETE_UPLOADS", "100"))


# ========================================
# 回答模式配置
# ========================================
# 自动模式：根据问题自动选择知识库或纯聊天
# 说明：常量定义，无需配置
ANSWER_MODE_AUTO = "auto"

# 仅使用知识库回答（找不到相关信息时回复不知道）
# 说明：常量定义，无需配置
ANSWER_MODE_KNOWLEDGE = "knowledge"

# 纯聊天模式（不使用知识库，直接用 LLM 回答）
# 说明：常量定义，无需配置
ANSWER_MODE_CHAT = "chat"

# 支持的回答模式集合（用于验证用户输入）
# 说明：常量定义，无需配置
SUPPORTED_ANSWER_MODES = {
    ANSWER_MODE_AUTO,
    ANSWER_MODE_KNOWLEDGE,
    ANSWER_MODE_CHAT,
}


# ========================================
# 聊天模型配置
# ========================================
# Ollama 本地聊天模型名称（需要先在 Ollama 中拉取该模型）
# 需要配置：本地部署的模型名称，如 "qwen3.5:9b"
LOCAL_CHAT_MODEL_NAME = os.getenv("RAG_LOCAL_MODEL", "qwen3.5:9b")

# 通义千问远程模型名称（阿里云 DashScope 服务）
# 需要配置：使用的云端模型，如 "qwen-max"
REMOTE_CHAT_MODEL_NAME = os.getenv("RAG_CHAT_MODEL", "qwen-max")

# 嵌入模型名称（与上面的 OLLAMA_EMBEDDING_FUNCTION 保持一致）
# 需要配置：用于文本向量化的模型
EMBEDDING_MODEL_NAME = os.getenv("RAG_EMBEDDING_MODEL", "qwen3-embedding:latest")

# Ollama 服务地址（本地部署时通常为 http://localhost:11434）
# 需要配置：Ollama 运行的服务器地址
OLLAMA_BASE_URL = os.getenv("RAG_OLLAMA_BASE_URL", "http://localhost:11434")

# 通义千问 API 密钥（在阿里云 DashScope 控制台获取，https://dashscope.console.aliyun.com/）
# 需要配置：阿里云 API Key，用于调用通义千问
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")


# ========================================
# Redis 配置
# ========================================
# Redis 连接 URL（格式：redis://[密码@]主机:端口/数据库编号）
# 需要配置：Redis 服务器地址和认证信息
REDIS_URL = os.getenv("RAG_REDIS_URL", "redis://127.0.0.1:6379/0").strip()

# Redis 键名前缀，用于隔离不同应用的缓存数据
# 需要配置：多个应用共用 Redis 时设置不同前缀
REDIS_KEY_PREFIX = os.getenv("RAG_REDIS_KEY_PREFIX", "rag").strip() or "rag"


# ========================================
# RabbitMQ 消息队列配置
# ========================================
# RabbitMQ 连接 URL（格式：amqp://用户名:密码@主机:端口/虚拟主机）
# 需要配置：RabbitMQ 服务器地址和认证信息
RABBITMQ_URL = os.getenv("RAG_RABBITMQ_URL", "amqp://guest:guest@127.0.0.1:5672/").strip()

# 是否启用 RabbitMQ 消息队列（False=使用同步上传，True=使用异步队列处理）
# 需要配置：大文件上传建议开启异步处理
RABBITMQ_ENABLED = env_bool("RAG_RABBITMQ_ENABLED", False)

# 文件上传队列名称（RabbitMQ 中的队列名）
# 说明：常量定义，无需配置
RABBITMQ_QUEUE_NAME = "rag.file.upload"

# 预取消息数量（Worker 一次从队列中获取的消息数，1=逐个处理）
# 需要配置：控制并发处理数量
RABBITMQ_PREFETCH_COUNT = 1


# ========================================
# 安全与速率限制配置
# ========================================
# 是否信任代理服务器传递的 IP 头（使用 Nginx 等反向代理时开启）
# 需要配置：使用反向代理时设为 True
TRUST_PROXY_HEADERS = env_bool("RAG_TRUST_PROXY_HEADERS", False)

# 受信任的代理服务器 IP 列表（只有这些 IP 传来的 X-Forwarded-For 才被信任）
# 需要配置：反向代理服务器的 IP 地址
TRUSTED_PROXY_IPS = {
    item.strip()
    for item in os.getenv("RAG_TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
    if item.strip()
}

# 登录速率限制：时间窗口（秒），在此窗口内最多允许多少次登录尝试
# 需要配置：防止暴力破解，300秒 = 5分钟
LOGIN_RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("RAG_LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300")
)

# 登录速率限制：最大尝试次数（超过后锁定）
# 需要配置：允许的最大登录失败次数
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = int(
    os.getenv("RAG_LOGIN_RATE_LIMIT_MAX_ATTEMPTS", "5")
)

# 注册速率限制：时间窗口（秒）
# 需要配置：防止恶意注册，1800秒 = 30分钟
REGISTER_RATE_LIMIT_WINDOW_SECONDS = int(
    os.getenv("RAG_REGISTER_RATE_LIMIT_WINDOW_SECONDS", "1800")
)

# 注册速率限制：最大尝试次数
# 需要配置：允许的最大注册次数
REGISTER_RATE_LIMIT_MAX_ATTEMPTS = int(
    os.getenv("RAG_REGISTER_RATE_LIMIT_MAX_ATTEMPTS", "5")
)

# 会话缓存过期时间（秒），用户多久不操作后需要重新登录
# 需要配置：会话保持时间，180秒 = 3分钟
SESSION_CACHE_TTL_SECONDS = int(os.getenv("RAG_SESSION_CACHE_TTL_SECONDS", "180"))

# 上传注册表过期时间（秒），上传任务记录多久后被视为失效
# 需要配置：上传任务超时时间，1800秒 = 30分钟
UPLOAD_REGISTRY_STALE_SECONDS = int(
    os.getenv("RAG_UPLOAD_REGISTRY_STALE_SECONDS", "1800")
)


# ========================================
# 聊天模型提供商配置
# ========================================
# 是否使用本地聊天模型（True=使用 Ollama，False=使用通义千问）
# 需要配置：选择模型运行方式
USE_LOCAL_CHAT_MODEL = env_bool("RAG_USE_LOCAL_CHAT_MODEL", False)

# 聊天模型提供商标识符
# 说明：常量定义，无需配置
CHAT_MODEL_PROVIDER_OLLAMA = "ollama"  # Ollama 本地模型
CHAT_MODEL_PROVIDER_TONGYI = "tongyi"  # 通义千问远程模型

# 支持的聊天模型提供商集合（用于验证配置）
# 说明：常量定义，无需配置
SUPPORTED_CHAT_MODEL_PROVIDERS = {
    CHAT_MODEL_PROVIDER_OLLAMA,
    CHAT_MODEL_PROVIDER_TONGYI,
}


def build_chat_model_id(provider: str, model_name: str) -> str:
    """构建模型 ID（格式：provider:model_name）"""
    return f"{provider}:{model_name.strip()}"


def build_chat_model_label(provider: str, model_name: str) -> str:
    """构建模型显示标签"""
    provider_label = "Ollama" if provider == CHAT_MODEL_PROVIDER_OLLAMA else "通义千问"
    return f"{provider_label} {model_name}"


def parse_chat_model_option(raw_option: str) -> dict | None:
    """解析模型选项字符串（格式：id|label）"""
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
    """从环境变量构建模型选项列表"""
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


# 构建模型选项列表
CHAT_MODEL_OPTIONS = build_chat_model_options()

# 模型选项 ID 映射
CHAT_MODEL_OPTION_BY_ID = {option["id"]: option for option in CHAT_MODEL_OPTIONS}

# 默认模型 ID
DEFAULT_CHAT_MODEL_ID = (
    build_chat_model_id(CHAT_MODEL_PROVIDER_OLLAMA, LOCAL_CHAT_MODEL_NAME)
    if USE_LOCAL_CHAT_MODEL
    else build_chat_model_id(CHAT_MODEL_PROVIDER_TONGYI, REMOTE_CHAT_MODEL_NAME)
)
if DEFAULT_CHAT_MODEL_ID not in CHAT_MODEL_OPTION_BY_ID and CHAT_MODEL_OPTIONS:
    DEFAULT_CHAT_MODEL_ID = CHAT_MODEL_OPTIONS[0]["id"]


def normalize_chat_model_id(model_id: str | None) -> str:
    """标准化模型 ID"""
    candidate_id = str(model_id or DEFAULT_CHAT_MODEL_ID).strip()
    if candidate_id in CHAT_MODEL_OPTION_BY_ID:
        return candidate_id
    return DEFAULT_CHAT_MODEL_ID


def get_chat_model_option(model_id: str | None = None) -> dict:
    """获取模型选项配置"""
    normalized_model_id = normalize_chat_model_id(model_id)
    return CHAT_MODEL_OPTION_BY_ID[normalized_model_id]


@lru_cache(maxsize=16)
def get_chat_model(model_id: str | None = None):
    """获取聊天模型实例（带缓存）"""
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


# 默认模型选项
DEFAULT_CHAT_MODEL_OPTION = get_chat_model_option(DEFAULT_CHAT_MODEL_ID)

# 当前激活的模型名称和提供商
ACTIVE_CHAT_MODEL_NAME = DEFAULT_CHAT_MODEL_OPTION["model"]
ACTIVE_CHAT_MODEL_PROVIDER = DEFAULT_CHAT_MODEL_OPTION["provider_label"]


# ========================================
# 会话默认配置
# ========================================
# 默认会话 ID（用于初始化 LangGraph 状态图）
# 需要配置：测试时使用的默认会话 ID
DEFAULT_SESSION_CONFIG = {
    "configurable": {
        "session_id": os.getenv("RAG_SESSION_ID", "hunter1"),
    }
}


# ========================================
# API 认证与安全配置
# ========================================
# API JWT 签名密钥（必须配置，长度至少 32 字符，建议使用随机生成的强密钥）
# 需要配置：生成方法: python -c 'import secrets; print(secrets.token_hex(32))'
API_SECRET_KEY = os.getenv("RAG_API_SECRET_KEY", "").strip()

# JWT 签名算法（默认 HS256，对称加密算法）
# 需要配置：通常保持 HS256 即可
API_JWT_ALGORITHM = os.getenv("RAG_API_JWT_ALGORITHM", "HS256")

# JWT 签发者标识（用于验证 Token 来源）
# 需要配置：标识 Token 的签发系统
API_JWT_ISSUER = os.getenv("RAG_API_JWT_ISSUER", "rag-api").strip() or "rag-api"

# JWT 目标受众（Token 的预期接收者）
# 需要配置：标识 Token 的使用方
API_JWT_AUDIENCE = os.getenv("RAG_API_JWT_AUDIENCE", "rag-frontend").strip() or "rag-frontend"

# Access Token 过期时间（分钟），默认 480 分钟（8 小时）
# 需要配置：Token 有效期，根据安全要求调整
API_ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("RAG_API_ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

# 初始化管理员账号：显示名称
# 需要配置：管理员显示名称
ADMIN_BOOTSTRAP_NAME = os.getenv("RAG_ADMIN_NAME", "系统管理员").strip() or "系统管理员"

# 初始化管理员账号：邮箱（必须配置，用于登录管理后台）
# 需要配置：管理员邮箱，用于登录
ADMIN_BOOTSTRAP_EMAIL = os.getenv("RAG_ADMIN_EMAIL", "").strip().lower()

# 初始化管理员账号：密码（必须配置，生产环境请使用强密码）
# 需要配置：管理员初始密码
ADMIN_BOOTSTRAP_PASSWORD = os.getenv("RAG_ADMIN_PASSWORD", "").strip()


# ========================================
# CORS 跨域配置
# ========================================
# 允许的跨域来源列表（前端地址，多个用逗号分隔）
# 需要配置：前端部署地址，多个地址用逗号分隔
API_CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "RAG_API_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",  # Vite 开发服务器地址
    ).split(",")
    if origin.strip()
]

# 允许的跨域来源正则表达式（用于匹配动态域名，留空表示不使用正则匹配）
# 需要配置：如果需要匹配多个动态域名，可以设置正则表达式
API_CORS_ORIGIN_REGEX = os.getenv("RAG_API_CORS_ORIGIN_REGEX", "").strip() or None


# ========================================
# 工具函数
# ========================================

def sanitize_user_key(user_id: str | None) -> str:
    """清理用户 ID 用于生成集合名（只保留字母数字）"""
    if not user_id:
        return "default"

    normalized = "".join(character for character in user_id.lower() if character.isalnum())
    return (normalized or "default")[:24]


def build_user_collection_name(user_id: str | None) -> str:
    """为用户构建独立的向量集合名"""
    if not user_id:
        return COLLECTION_NAME

    suffix = sanitize_user_key(user_id)
    collection_name = f"{COLLECTION_NAME}_{suffix}"[:63]
    return collection_name.rstrip("_-")


def build_chroma_kwargs(collection_name: str, embedding_function):
    """根据运行模式构建 ChromaDB 连接参数"""
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
    """验证服务器配置是否符合安全要求"""
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
