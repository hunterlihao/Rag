import uvicorn

from rag_app import config
from rag_app.utils.logging_config import configure_logging

configure_logging()

try:
    from rag_app.api.app import app  # noqa: E402
    print(f"✓ 成功导入 app 对象: {type(app)}")
except Exception as e:
    print(f"✗ 导入 app 失败: {e}")
    import traceback
    traceback.print_exc()
    raise


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
