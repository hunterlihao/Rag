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
    """优化 #9: 使用聚合查询替代全表扫描，避免 N+1 查询问题"""
    try:
        engine = create_engine(
            config.POSTGRES_CONNECTION_URL,
            **config.POSTGRES_ENGINE_ARGS,
        )
        
        # 使用子查询获取每个会话的第一条用户消息和最后一条消息
        sql = text("""
            WITH session_stats AS (
                SELECT 
                    session_id,
                    COUNT(*) as message_count,
                    MAX(id) as last_message_id
                FROM {table_name}
                GROUP BY session_id
            ),
            first_user_messages AS (
                SELECT DISTINCT ON (session_id)
                    session_id,
                    message->'data'->>'content' as first_user_content
                FROM {table_name}
                WHERE message->>'type' = 'human'
                    AND message->'data'->>'content' IS NOT NULL
                    AND message->'data'->>'content' != ''
                ORDER BY session_id, id ASC
            ),
            last_messages AS (
                SELECT DISTINCT ON (session_id)
                    session_id,
                    message->'data'->>'content' as last_content
                FROM {table_name}
                ORDER BY session_id, id DESC
            )
            SELECT 
                ss.session_id,
                ss.message_count,
                ss.last_message_id,
                fum.first_user_content,
                lm.last_content
            FROM session_stats ss
            LEFT JOIN first_user_messages fum ON ss.session_id = fum.session_id
            LEFT JOIN last_messages lm ON ss.session_id = lm.session_id
            ORDER BY ss.last_message_id DESC
            LIMIT :limit
        """.format(table_name=config.CHAT_HISTORY_TABLE_NAME))

        sessions = []
        with engine.connect() as connection:
            rows = connection.execute(sql, {"limit": limit}).fetchall()

        for row in rows:
            # 提取会话标题（从第一条用户消息）
            title = "新会话"
            if row.first_user_content:
                title = truncate_text(str(row.first_user_content), 18)
            
            # 提取预览（从最后一条消息）
            preview = "还没有消息"
            if row.last_content:
                preview = truncate_text(str(row.last_content), 34)
            
            sessions.append({
                "session_id": row.session_id,
                "title": title,
                "preview": preview,
                "message_count": row.message_count,
                "last_message_id": row.last_message_id,
            })

        return sessions
    except Exception as exc:
        raise RuntimeError(
            "读取 PostgreSQL 会话列表失败，请确认数据库已启动并且历史表可访问。"
        ) from exc


def truncate_text(text_value: str, max_length: int) -> str:
    compact_text = " ".join(text_value.split())
    if len(compact_text) <= max_length:
        return compact_text
    return compact_text[: max_length - 1] + "…"
