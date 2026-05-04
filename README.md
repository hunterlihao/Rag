# RAG Demo

这是一个基础的 LangChain RAG 示例项目。当前仓库里保留 Python 侧的 FastAPI RAG 服务代码，以及一个独立的 Vue + Element Plus 前端工作台。

## 目录结构

```text
RAG/
├─ frontend/                  # 独立前端（Vue 3 + Element Plus）
├─ app_api.py                  # FastAPI 后端入口
├─ README.md
├─ rag_app/
│  ├─ api/                     # FastAPI 路由层
│  ├─ loaders/                 # 文件解析层
│  ├─ services/                # 业务服务层
│  ├─ storage/                 # 持久化层
│  └─ config.py                # 统一配置
├─ chroma_db/                  # Chroma 向量库持久化目录
├─ chat_history/               # 历史本地目录（旧实现遗留）
└─ *.text                      # 去重文件等运行期产物
```

## 启动方式

先安装 Python 依赖：

```powershell
D:\development\Anaconda3\envs\python-3-13-11\python.exe -m pip install -r D:\code\python-code\AIDemo\RAG\requirements.txt
```

启动后端 API：

```powershell
D:\development\Anaconda3\envs\python-3-13-11\python.exe D:\code\python-code\AIDemo\RAG\app_api.py
```

再启动前端：

```powershell
cd D:\code\python-code\AIDemo\RAG\frontend
pnpm install
pnpm dev
```

前端默认通过 Vite 代理请求 `/api`，本地会转发到 `http://127.0.0.1:8520`。

## Chroma Docker

如果你想先单独把 Chroma 跑在 Docker 里，项目根目录已经提供：

```powershell
docker compose -f D:\code\python-code\AIDemo\RAG\docker-compose.chroma.yml up -d
```

说明：

- 使用 Docker 卷 `chroma_data` 做持久化存储
- 容器内端口是 `8000`
- 宿主机映射为 `8001`

停止：

```powershell
docker compose -f D:\code\python-code\AIDemo\RAG\docker-compose.chroma.yml down
```

查看卷：

```powershell
docker volume inspect chroma_data
```

现在项目已经支持通过 `.env` 在两种模式之间切换：

- `RAG_CHROMA_MODE=local`：使用本地目录持久化
- `RAG_CHROMA_MODE=http`：连接 Docker / 远程 Chroma 服务
- `RAG_CHROMA_HOST=127.0.0.1`
- `RAG_CHROMA_PORT=8001`
- `RAG_CHROMA_SSL=false`

当前这套本地配置已经切到 Docker Chroma，对应你在 WSL / Docker 里映射到 Windows 的 `127.0.0.1:8001`。

## Redis Docker

如果你想把 Redis 也单独跑在 Docker 里，项目根目录已经提供：

```powershell
docker compose -f D:\code\python-code\AIDemo\RAG\docker-compose.redis.yml up -d
```

说明：

- 使用 Docker 卷 `redis_data` 做持久化存储
- 默认开启 AOF 持久化
- 宿主机端口映射为 `6379`

停止：

```powershell
docker compose -f D:\code\python-code\AIDemo\RAG\docker-compose.redis.yml down
```

## 配置方式

- 项目启动时会自动读取根目录下的 `.env`。
- 模板文件在 `.env.example`，当前本地运行配置已经写入 `.env`。
- 如果要改 Chroma 连接方式、PostgreSQL、Ollama、模型名、分块参数、JWT 密钥、跨域地址、内网穿透来源正则或后端上传并发，直接修改 `.env` 即可。
- 后端日志已经统一为企业级结构化日志，默认输出到控制台和 `logs/rag-api.log`，每条请求日志都会带 `request_id`、`user_id`、客户端 IP、耗时和状态码。
- 日志相关配置：
  - `RAG_APP_NAME=rag-api`
  - `RAG_APP_ENV=local`
  - `RAG_LOG_LEVEL=INFO`
  - `RAG_LOG_FORMAT=spring`，控制文件日志格式，如需 JSON 结构化输出可改为 `json`
  - `RAG_LOG_CONSOLE_FORMAT=spring`，控制控制台日志格式，建议本地保持 `spring`
  - `RAG_LOG_COLOR_ENABLED=true`，控制台文本日志按级别着色，关闭可设为 `false`
  - `RAG_LOG_TO_FILE=true`
  - `RAG_LOG_DIR=logs`
  - `RAG_LOG_FILE_NAME=rag-api.log`
  - `RAG_LOG_MAX_BYTES=10485760`
  - `RAG_LOG_BACKUP_COUNT=10`
  - `RAG_LOG_ACCESS_ENABLED=false`
  - `RAG_LOG_SLOW_REQUEST_MS=2000`
- Redis 相关配置也集中在 `.env`：
  - `RAG_REDIS_URL=redis://127.0.0.1:6379/0`
  - `RAG_REDIS_KEY_PREFIX=rag`
  - `RAG_TRUST_PROXY_HEADERS=false`
  - `RAG_TRUSTED_PROXY_IPS=127.0.0.1,::1`
  - `RAG_LOGIN_RATE_LIMIT_WINDOW_SECONDS=300`
  - `RAG_LOGIN_RATE_LIMIT_MAX_ATTEMPTS=5`
  - `RAG_REGISTER_RATE_LIMIT_WINDOW_SECONDS=1800`
  - `RAG_REGISTER_RATE_LIMIT_MAX_ATTEMPTS=5`
  - `RAG_SESSION_CACHE_TTL_SECONDS=180`
  - `RAG_UPLOAD_REGISTRY_STALE_SECONDS=1800`
- 当前默认已经开启增强检索：更小分块、更多召回、相似度阈值、MMR、查询改写、LLM rerank。
- 新前端页面已经打通真实后端：左侧会话历史，中间问答，右侧上传文件；当模型回答中时，上传区会自动锁定。
- 后端现在依赖 Redis 做登录限流、JWT 吊销和会话列表缓存；Redis 没启动时，后端会直接启动失败。
  如果你后端前面还有 Nginx / cpolar / 其他反向代理，需要显式开启 `RAG_TRUST_PROXY_HEADERS=true`，并把代理出口 IP 写到 `RAG_TRUSTED_PROXY_IPS`，否则后端不会信任 `X-Forwarded-For`。

## 模型切换

问答模型不再在代码里写死。后端会从 `.env` 的 `RAG_CHAT_MODEL_OPTIONS` 读取可选模型，前端会在聊天输入框发送按钮左侧提供“模型”下拉选择。

配置格式：

```env
RAG_CHAT_MODEL_OPTIONS=provider:model|显示名称,provider:model|显示名称
```

当前支持的 `provider`：

- `tongyi`：通义千问 / DashScope，使用 `DASHSCOPE_API_KEY`
- `ollama`：本地 Ollama，使用 `RAG_OLLAMA_BASE_URL`

示例：

```env
RAG_CHAT_MODEL_OPTIONS=tongyi:qwen-max|通义千问 qwen-max,tongyi:qwen-plus|通义千问 qwen-plus,ollama:qwen3.5:9b|Ollama qwen3.5:9b
```

新增模型步骤：

1. 在 `.env` 的 `RAG_CHAT_MODEL_OPTIONS` 里追加一个模型项。
2. 如果是 Ollama 模型，先确保本机已经拉取，例如 `ollama pull qwen3.5:9b`。
3. 重启后端 API。
4. 刷新前端页面，在聊天框右下角“模型”菜单里选择新模型。

默认模型规则：

- `RAG_USE_LOCAL_CHAT_MODEL=false` 时，默认优先使用 `RAG_CHAT_MODEL` 对应的通义模型。
- `RAG_USE_LOCAL_CHAT_MODEL=true` 时，默认优先使用 `RAG_LOCAL_MODEL` 对应的 Ollama 模型。
- 如果默认模型没有出现在 `RAG_CHAT_MODEL_OPTIONS` 中，后端会使用列表里的第一个模型作为兜底默认。

## 余弦相似度位置

- 余弦相似度配置入口在 `rag_app/config.py` 的 `VECTOR_DISTANCE_SPACE` 和 `COLLECTION_METADATA`。
- 实际传给 Chroma 的位置有两处：
  - `rag_app/services/vector_store.py`
  - `rag_app/services/knowledge_base.py`
- 当前默认值来自 `.env` 里的 `RAG_VECTOR_DISTANCE_SPACE=cosine`。

## 检索增强参数

- `RAG_CHUNK_SIZE=500`
- `RAG_CHUNK_OVERLAP=100`
- `RAG_RETRIEVAL_TOP_K=5`
- `RAG_RETRIEVAL_FETCH_K=20`
- `RAG_SIMILARITY_THRESHOLD_ENABLED=true`
- `RAG_SIMILARITY_THRESHOLD=0.35`
- `RAG_MMR_ENABLED=true`
- `RAG_MMR_LAMBDA_MULT=0.6`
- `RAG_MMR_CANDIDATE_K=8`
- `RAG_QUERY_REWRITE_ENABLED=true`
- `RAG_QUERY_REWRITE_HISTORY_TURNS=3`
- `RAG_RERANK_ENABLED=true`
- `RAG_RERANK_TOP_K=5`
- `RAG_DEBUG_RETRIEVAL=false`
- `RAG_UPLOAD_MAX_WORKERS=4`
- `RAG_REDIS_URL=redis://127.0.0.1:6379/0`
- `RAG_TRUST_PROXY_HEADERS=false`
- `RAG_TRUSTED_PROXY_IPS=127.0.0.1,::1`
- `RAG_REGISTER_RATE_LIMIT_WINDOW_SECONDS=1800`
- `RAG_REGISTER_RATE_LIMIT_MAX_ATTEMPTS=5`
- `RAG_SESSION_CACHE_TTL_SECONDS=180`
- `RAG_UPLOAD_REGISTRY_STALE_SECONDS=1800`
- `RAG_API_CORS_ORIGIN_REGEX=https://.*\\.cpolar\\.top`
- `RAG_CHROMA_MODE=http`
- `RAG_CHROMA_HOST=127.0.0.1`
- `RAG_CHROMA_PORT=8001`

> 调整分块参数或向量检索策略后，建议清空旧的 `chroma_db` 后重新导入知识库，避免旧分块继续影响召回效果。

## 当前职责划分

- `rag_app/api`：负责 FastAPI 路由、鉴权依赖、会话问答、知识库上传和管理接口。
- `rag_app/services`：负责 RAG 检索链、知识入库、向量库访问。
- `rag_app/loaders`：负责 pdf、docx、excel、txt、md、csv 的文本提取。
- `rag_app/storage`：负责 PostgreSQL 对话历史持久化。
- `rag_app/config.py`：集中管理模型、数据库、路径和上传支持格式等配置。
