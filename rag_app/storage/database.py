from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

from rag_app import config

engine = create_engine(
    config.POSTGRES_CONNECTION_URL,
    **config.POSTGRES_ENGINE_ARGS,
)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)
Base = declarative_base()
database_initialized = False


def ensure_schema_updates():
    statements = [
        """
        ALTER TABLE IF EXISTS rag_user_sessions
        ADD COLUMN IF NOT EXISTS message_count INTEGER
        """,
        """
        ALTER TABLE IF EXISTS rag_user_sessions
        ADD COLUMN IF NOT EXISTS last_message_preview TEXT
        """,
        """
        ALTER TABLE IF EXISTS rag_users
        ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE
        """,
        """
        ALTER TABLE IF EXISTS rag_users
        ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE IF EXISTS rag_uploaded_documents
        ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64)
        """,
        """
        ALTER TABLE IF EXISTS rag_uploaded_documents
        ADD COLUMN IF NOT EXISTS vector_doc_id VARCHAR(64)
        """,
        """
        ALTER TABLE IF EXISTS rag_uploaded_content_registry
        ADD COLUMN IF NOT EXISTS content_sha256 VARCHAR(64)
        """,
        """
        ALTER TABLE IF EXISTS rag_uploaded_content_registry
        ADD COLUMN IF NOT EXISTS vector_doc_id VARCHAR(64)
        """,
        """
        ALTER TABLE IF EXISTS rag_uploaded_content_registry
        DROP CONSTRAINT IF EXISTS uq_rag_uploaded_content_registry_user_md5
        """,
        """
        DROP INDEX IF EXISTS uq_rag_uploaded_content_registry_user_md5
        """,
        """
        ALTER TABLE IF EXISTS rag_uploaded_documents
        DROP COLUMN IF EXISTS content_md5
        """,
        """
        ALTER TABLE IF EXISTS rag_uploaded_content_registry
        DROP COLUMN IF EXISTS content_md5
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_rag_uploaded_content_registry_user_sha256
        ON rag_uploaded_content_registry (uploader_id, content_sha256)
        WHERE content_sha256 IS NOT NULL
        """,
        """
        ALTER TABLE IF EXISTS rag_uploaded_content_registry
        ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'processing'
        """,
        """
        ALTER TABLE IF EXISTS rag_uploaded_content_registry
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
        """,
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def init_database():
    global database_initialized
    if database_initialized:
        return

    from rag_app.storage import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    ensure_schema_updates()
    database_initialized = True


def get_db():
    init_database()

    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
