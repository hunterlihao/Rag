import contextvars
import json
import logging
import logging.config
import re
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from rag_app import config

request_id_var = contextvars.ContextVar("request_id", default="-")
user_id_var = contextvars.ContextVar("user_id", default="-")
client_ip_var = contextvars.ContextVar("client_ip", default="-")

SENSITIVE_KEYWORDS = (
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "cookie",
    "set-cookie",
)
STANDARD_LOG_RECORD_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}

LEVEL_COLORS = {
    logging.DEBUG: "\033[90m",
    logging.INFO: "\033[32m",
    logging.WARNING: "\033[33m",
    logging.ERROR: "\033[31m",
    logging.CRITICAL: "\033[1;31m",
}
ANSI_RESET = "\033[0m"
ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def set_log_context(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    client_ip: str | None = None,
):
    tokens = {}
    if request_id is not None:
        tokens["request_id"] = request_id_var.set(request_id or "-")
    if user_id is not None:
        tokens["user_id"] = user_id_var.set(user_id or "-")
    if client_ip is not None:
        tokens["client_ip"] = client_ip_var.set(client_ip or "-")
    return tokens


def reset_log_context(tokens: dict[str, contextvars.Token]):
    for key, token in tokens.items():
        if key == "request_id":
            request_id_var.reset(token)
        elif key == "user_id":
            user_id_var.reset(token)
        elif key == "client_ip":
            client_ip_var.reset(token)


def get_request_id() -> str:
    return request_id_var.get()


def mask_sensitive_value(value: Any) -> Any:
    if value is None:
        return None
    text = str(value)
    if len(text) <= 8:
        return "***"
    return f"{text[:4]}...{text[-4:]}"


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE_RE.sub("", text)


def sanitize_log_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key)
            if any(keyword in key_text.lower() for keyword in SENSITIVE_KEYWORDS):
                sanitized[key_text] = mask_sensitive_value(item)
            else:
                sanitized[key_text] = sanitize_log_value(item)
        return sanitized

    if isinstance(value, (list, tuple, set)):
        return [sanitize_log_value(item) for item in value]

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, str):
        return strip_ansi(value)

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return str(value)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.user_id = user_id_var.get()
        record.client_ip = client_ip_var.get()
        record.app = config.APP_NAME
        record.env = config.APP_ENV
        return True


class MaxLevelFilter(logging.Filter):
    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self.max_level


class MinLevelFilter(logging.Filter):
    def __init__(self, min_level: int):
        super().__init__()
        self.min_level = min_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= self.min_level


def color_text(text: str, levelno: int) -> str:
    color = LEVEL_COLORS.get(levelno)
    if not color:
        return text
    return f"{color}{text}{ANSI_RESET}"


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.message = strip_ansi(record.getMessage())
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
            "app": getattr(record, "app", config.APP_NAME),
            "env": getattr(record, "env", config.APP_ENV),
            "request_id": getattr(record, "request_id", "-"),
            "user_id": getattr(record, "user_id", "-"),
            "client_ip": getattr(record, "client_ip", "-"),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.threadName,
        }

        for key, value in record.__dict__.items():
            if key in STANDARD_LOG_RECORD_KEYS or key in payload:
                continue
            if key.startswith("_"):
                continue
            if any(keyword in key.lower() for keyword in SENSITIVE_KEYWORDS):
                payload[key] = mask_sensitive_value(value)
            else:
                payload[key] = sanitize_log_value(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


class ConsoleLogFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            "%(asctime)s %(levelname)s [%(request_id)s] "
            "%(name)s:%(lineno)d user=%(user_id)s ip=%(client_ip)s - %(message)s"
        )

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        if getattr(record, "_console_color", False):
            return color_text(line, record.levelno)
        return line


class SpringBootLogFormatter(logging.Formatter):
    LEVEL_WIDTH = 5

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:23]

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        timestamp = self.formatTime(record)
        level = record.levelname.ljust(self.LEVEL_WIDTH)
        if getattr(record, "_console_color", False):
            level = color_text(level, record.levelno)
        thread_name = record.threadName[:24]
        logger_name = record.name
        trace = ""
        request_id = getattr(record, "request_id", "-")
        user_id = getattr(record, "user_id", "-")
        if request_id != "-" or user_id != "-":
            trace = f" [{request_id}/{user_id}]"

        line = (
            f"{timestamp} {level} {record.process} --- "
            f"[{thread_name}] {logger_name}{trace} : {message}"
        )
        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        if record.stack_info:
            line = f"{line}\n{self.formatStack(record.stack_info)}"
        return line


def build_handler(
    formatter: logging.Formatter,
    stream: bool = False,
    *,
    stream_target=None,
    console_color: bool = False,
):
    if stream:
        handler = logging.StreamHandler(stream_target)
    else:
        log_dir = Path(config.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / config.LOG_FILE_NAME,
            maxBytes=max(config.LOG_MAX_BYTES, 1024 * 1024),
            backupCount=max(config.LOG_BACKUP_COUNT, 1),
            encoding="utf-8",
        )
    handler.setFormatter(formatter)
    handler.addFilter(ContextFilter())
    handler.addFilter(ConsoleColorFilter(console_color))
    return handler


class ConsoleColorFilter(logging.Filter):
    def __init__(self, enabled: bool):
        super().__init__()
        self.enabled = enabled

    def filter(self, record: logging.LogRecord) -> bool:
        record._console_color = self.enabled
        return True


def configure_logging():
    def build_formatter(log_format: str) -> logging.Formatter:
        if log_format == "json":
            return JsonLogFormatter()
        if log_format == "text":
            return ConsoleLogFormatter()
        return SpringBootLogFormatter()

    console_formatter = build_formatter(config.LOG_CONSOLE_FORMAT)
    file_formatter = build_formatter(config.LOG_FORMAT)
    color_enabled = config.LOG_CONSOLE_FORMAT in {"text", "spring"} and config.LOG_COLOR_ENABLED
    stdout_handler = build_handler(
        console_formatter,
        stream=True,
        stream_target=sys.stdout,
        console_color=color_enabled,
    )
    stdout_handler.addFilter(MaxLevelFilter(logging.ERROR))

    stderr_handler = build_handler(
        console_formatter,
        stream=True,
        stream_target=sys.stderr,
        console_color=color_enabled,
    )
    stderr_handler.addFilter(MinLevelFilter(logging.ERROR))

    handlers = [stdout_handler, stderr_handler]
    if config.LOG_TO_FILE:
        handlers.append(build_handler(file_formatter, stream=False))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(config.LOG_LEVEL)
    for handler in handlers:
        root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(config.LOG_LEVEL)

    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
