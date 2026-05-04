import uvicorn

from rag_app import config
from rag_app.utils.logging_config import configure_logging

configure_logging()

from rag_app.api.app import app  # noqa: E402


if __name__ == "__main__":
    uvicorn.run(
        "app_api:app",
        host="0.0.0.0",
        port=8520,
        reload=True,
        log_config=None,
        access_log=False,
        log_level=config.LOG_LEVEL.lower(),
    )
