import json

from langchain_community.chat_message_histories import SQLChatMessageHistory
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from rag_app import config


def get_history(session_id: str) -> SQLChatMessageHistory:
    try:
        return SQLChatMessageHistory(
            session_id=session_id,
            connection=config.POSTGRES_CONNECTION_URL,
            table_name=config.CHAT_HISTORY_TABLE_NAME,
            engine_args=config.POSTGRES_ENGINE_ARGS,
        )
    except Exception as exc:
        raise RuntimeError(
            "PostgreSQL 对话历史初始化失败，请确认 PostgreSQL 服务已启动，"
            f"并检查 {config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB} "
            "是否为正确的连接信息。"
        ) from exc


def load_session_messages(session_id: str) -> list[dict]:
    history = get_history(session_id)
    ui_messages = []
    for index, message in enumerate(history.messages, start=1):
        role = "user" if message.type == "human" else "assistant" if message.type == "ai" else None
        if role is None:
            continue
        msg_data = {
            "id": f"{session_id}-{index}",
            "role": role,
            "content": str(message.content),
        }
        if role == "assistant" and message.additional_kwargs:
            sources = message.additional_kwargs.get("sources")
            if sources:
                msg_data["sources"] = sources
        ui_messages.append(msg_data)
    return ui_messages


def delete_session_messages(database: Session, session_id: str):
    sql = text(
        f"DELETE FROM {config.CHAT_HISTORY_TABLE_NAME} "
        "WHERE session_id = :session_id"
    )
    database.execute(sql, {"session_id": session_id})


def list_sessions(limit: int = 30) -> list[dict]:
    try:
        engine = create_engine(
            config.POSTGRES_CONNECTION_URL,
            **config.POSTGRES_ENGINE_ARGS,
        )
        row_limit = max(limit * 40, 200)
        sql = text(
            f"SELECT id, session_id, message FROM {config.CHAT_HISTORY_TABLE_NAME} "
            "ORDER BY id DESC LIMIT :row_limit"
        )

        sessions = {}
        with engine.connect() as connection:
            rows = connection.execute(sql, {"row_limit": row_limit}).fetchall()

        for row in rows:
            session_id = row.session_id
            payload = json.loads(row.message)
            content = str(payload.get("data", {}).get("content", "")).strip()
            role = payload.get("type")

            if session_id not in sessions:
                sessions[session_id] = {
                    "session_id": session_id,
                    "title": "新会话",
                    "preview": "还没有消息",
                    "message_count": 0,
                    "last_message_id": row.id,
                }

            sessions[session_id]["message_count"] += 1

            if content and sessions[session_id]["preview"] == "还没有消息":
                sessions[session_id]["preview"] = truncate_text(content, 34)

            if role == "human" and content and sessions[session_id]["title"] == "新会话":
                sessions[session_id]["title"] = truncate_text(content, 18)

        return list(sessions.values())[:limit]
    except Exception as exc:
        raise RuntimeError(
            "读取 PostgreSQL 会话列表失败，请确认数据库已启动并且历史表可访问。"
        ) from exc


def truncate_text(text_value: str, max_length: int) -> str:
    compact_text = " ".join(text_value.split())
    if len(compact_text) <= max_length:
        return compact_text
    return compact_text[: max_length - 1] + "…"
