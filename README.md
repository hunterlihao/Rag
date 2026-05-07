# RAG Knowledge Workspace

一个开箱即用的本地 RAG 知识库项目。后端使用 FastAPI、LangChain、Chroma、PostgreSQL、Redis，前端使用 Vue 3、Vite、Element Plus。你可以上传文档，系统会解析文本、切分片段、生成向量并写入向量库，然后在聊天工作台中基于知识库进行问答。

项目默认支持：

- 多用户注册、登录、JWT 鉴权和管理员账号
- 知识库文件上传、去重、删除和向量化入库
- PDF、Word、Excel、CSV、Markdown、TXT 文本提取
- Chroma 向量库，本地持久化或 HTTP 服务两种模式
- Ollama 本地 embedding
- DashScope / 通义千问或 Ollama 本地模型问答
- Redis 登录限流、会话缓存和 Token 吊销
- Vue 前端聊天工作台和知识库管理面板

## 技术栈

| 模块 | 技术 |
| --- | --- |
| 后端 API | FastAPI、Uvicorn、Pydantic |
| RAG | LangChain、langchain-chroma、langchain-ollama |
| 向量库 | Chroma |
| 数据库 | PostgreSQL、SQLAlchemy |
| 缓存 | Redis |
| 前端 | Vue 3、Vite、Element Plus |
| 文档解析 | pypdf、python-docx、pandas、openpyxl、xlrd |

## 目录结构

```text
RAG/
├─ app_api.py                    # FastAPI 启动入口
├─ requirements.txt              # Python 依赖
├─ docker-compose.chroma.yml     # Chroma Docker 服务
├─ docker-compose.redis.yml      # Redis Docker 服务
├─ frontend/                     # Vue 3 前端
│  ├─ package.json
│  ├─ vite.config.js
│  └─ src/
└─ rag_app/
   ├─ api/                       # API 路由、鉴权、中间件
   ├─ loaders/                   # 文档解析
   ├─ services/                  # RAG、用户、知识库、Redis 业务逻辑
   ├─ storage/                   # 数据库模型和会话历史
   ├─ utils/                     # 日志、时间等工具
   └─ config.py                  # 环境变量配置中心
```

## 环境要求

建议使用下面的版本或更高版本：

- Python 3.11+
- Node.js 20+
- pnpm 9+
- PostgreSQL 14+
- Redis 7+
- Docker Desktop，可选，用来快速启动 Chroma 和 Redis
- Ollama，可选但推荐，用来跑本地 embedding 和本地聊天模型

如果你只想快速跑起来，推荐：

- PostgreSQL 使用本机安装或已有 Docker 服务
- Redis 使用本仓库的 `docker-compose.redis.yml`
- Chroma 使用本仓库的 `docker-compose.chroma.yml`
- embedding 使用 Ollama
- 聊天模型先用 DashScope，或者完全使用 Ollama 本地模型

## 快速开始

### 1. 克隆项目

```bash
git clone <your-repo-url>
cd RAG
```

### 2. 准备 Python 环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 启动 Redis 和 Chroma

项目已经提供 Docker Compose 文件：

```bash
docker compose -f docker-compose.redis.yml up -d
docker compose -f docker-compose.chroma.yml up -d
```

默认端口：

- Redis：`127.0.0.1:6379`
- Chroma：`127.0.0.1:8001`

如果你没有 Docker，也可以自己安装 Redis 和 Chroma，只要最后 `.env` 里的连接地址一致即可。

### 4. 准备 PostgreSQL

创建数据库和用户。下面是一个本地开发示例，你可以按自己的 PostgreSQL 配置调整：

```sql
CREATE DATABASE rag;
CREATE USER rag_user WITH PASSWORD 'change_me';
GRANT ALL PRIVILEGES ON DATABASE rag TO rag_user;
```

如果你直接使用本机已有的 `postgres` 用户，也可以只创建数据库：

```sql
CREATE DATABASE rag;
```

后端启动时会自动创建需要的数据表，并自动补齐历史版本字段。

### 5. 准备 Ollama 模型

项目默认使用 Ollama 生成 embedding：

```bash
ollama pull qwen3-embedding:latest
```

如果你想使用本地聊天模型，也需要拉取聊天模型，例如：

```bash
ollama pull qwen3.5:9b
```

确认 Ollama 服务已启动：

```bash
ollama list
```

默认 Ollama 地址是：

```text
http://localhost:11434
```

### 6. 配置后端 `.env`

复制示例配置：

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

然后打开 `.env`，至少修改这些配置：

```env
RAG_POSTGRES_HOST=127.0.0.1
RAG_POSTGRES_PORT=5432
RAG_POSTGRES_DB=rag
RAG_POSTGRES_USER=rag_user
RAG_POSTGRES_PASSWORD=change_me

RAG_REDIS_URL=redis://127.0.0.1:6379/0

RAG_CHROMA_MODE=http
RAG_CHROMA_HOST=127.0.0.1
RAG_CHROMA_PORT=8001
RAG_CHROMA_SSL=false

RAG_OLLAMA_BASE_URL=http://localhost:11434
RAG_EMBEDDING_MODEL=qwen3-embedding:latest

RAG_API_SECRET_KEY=请换成一段足够长的随机字符串
RAG_ADMIN_EMAIL=admin@example.com
RAG_ADMIN_PASSWORD=请换成你的管理员密码
```

生成 `RAG_API_SECRET_KEY` 的简单方式：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

如果使用 DashScope / 通义千问作为聊天模型，还需要配置：

```env
DASHSCOPE_API_KEY=你的 DashScope API Key
RAG_USE_LOCAL_CHAT_MODEL=false
RAG_CHAT_MODEL=qwen-max
```

如果想完全使用 Ollama 本地聊天模型，可以这样配置：

```env
DASHSCOPE_API_KEY=
RAG_USE_LOCAL_CHAT_MODEL=true
RAG_LOCAL_MODEL=qwen3.5:9b
RAG_CHAT_MODEL_OPTIONS=ollama:qwen3.5:9b|Ollama qwen3.5:9b
```

### 7. 启动后端

确保 Python 虚拟环境已激活，然后运行：

```bash
python app_api.py
```

启动成功后，后端地址是：

```text
http://127.0.0.1:8520
```

你可以访问健康检查接口：

```text
http://127.0.0.1:8520/api/health
```

首次启动时后端会做这些事：

- 校验 `.env` 中的必要配置
- 初始化 PostgreSQL 数据表
- 检查 Redis 是否可连接
- 创建或更新管理员账号
- 初始化 RAG 服务

### 8. 配置并启动前端

进入前端目录：

```bash
cd frontend
```

安装依赖：

```bash
pnpm install
```

复制前端配置：

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

本地开发时通常保持下面配置即可：

```env
VITE_API_BASE_URL=/api
VITE_PROXY_TARGET=http://127.0.0.1:8520
```

启动前端：

```bash
pnpm dev
```

打开：

```text
http://127.0.0.1:5173
```

使用 `.env` 中配置的管理员邮箱和密码登录。

## 跑通一次完整流程

1. 启动 PostgreSQL、Redis、Chroma、Ollama
2. 启动后端：`python app_api.py`
3. 启动前端：`cd frontend && pnpm dev`
4. 打开 `http://127.0.0.1:5173`
5. 使用管理员账号登录
6. 在右侧知识库面板上传一个 `.txt`、`.md` 或 `.pdf` 文件
7. 等待上传成功，系统会写入 Chroma 向量库
8. 在聊天框提问和文档相关的问题

如果回答能引用或利用刚上传的内容，说明 RAG 流程已经跑通。

## 重要配置说明

### 后端基础配置

| 变量 | 说明 |
| --- | --- |
| `RAG_APP_ENV` | 运行环境，例如 `local`、`production` |
| `RAG_API_SECRET_KEY` | JWT 签名密钥，必须设置，不能公开 |
| `RAG_API_ACCESS_TOKEN_EXPIRE_MINUTES` | 登录 Token 有效期 |
| `RAG_API_CORS_ORIGINS` | 允许访问 API 的前端地址 |
| `RAG_API_CORS_ORIGIN_REGEX` | 允许访问 API 的来源正则，可选 |

### 数据库和缓存

| 变量 | 说明 |
| --- | --- |
| `RAG_POSTGRES_HOST` | PostgreSQL 地址 |
| `RAG_POSTGRES_PORT` | PostgreSQL 端口 |
| `RAG_POSTGRES_DB` | 数据库名 |
| `RAG_POSTGRES_USER` | 数据库用户 |
| `RAG_POSTGRES_PASSWORD` | 数据库密码，不能公开 |
| `RAG_REDIS_URL` | Redis 连接地址 |
| `RAG_REDIS_KEY_PREFIX` | Redis key 前缀 |

### 向量库

| 变量 | 说明 |
| --- | --- |
| `RAG_CHROMA_MODE` | `local` 或 `http` |
| `RAG_CHROMA_HOST` | Chroma HTTP 服务地址 |
| `RAG_CHROMA_PORT` | Chroma HTTP 服务端口 |
| `RAG_CHROMA_SSL` | 是否使用 HTTPS 连接 Chroma |
| `RAG_COLLECTION_NAME` | Chroma collection 前缀 |
| `RAG_VECTOR_DISTANCE_SPACE` | 向量距离，默认 `cosine` |

`RAG_CHROMA_MODE=local` 时，Chroma 会使用项目根目录下的 `chroma_db/` 作为本地持久化目录。

`RAG_CHROMA_MODE=http` 时，后端会连接独立 Chroma 服务，适合 Docker 或远程部署。

### 模型配置

| 变量 | 说明 |
| --- | --- |
| `RAG_OLLAMA_BASE_URL` | Ollama 服务地址 |
| `RAG_EMBEDDING_MODEL` | embedding 模型名 |
| `RAG_USE_LOCAL_CHAT_MODEL` | 是否默认使用 Ollama 本地聊天模型 |
| `RAG_LOCAL_MODEL` | Ollama 本地聊天模型 |
| `RAG_CHAT_MODEL` | DashScope 聊天模型 |
| `RAG_CHAT_MODEL_OPTIONS` | 前端模型下拉菜单选项 |
| `DASHSCOPE_API_KEY` | DashScope API Key，不能公开 |

`RAG_CHAT_MODEL_OPTIONS` 格式：

```env
RAG_CHAT_MODEL_OPTIONS=provider:model|显示名称,provider:model|显示名称
```

当前支持：

- `tongyi`：DashScope / 通义千问
- `ollama`：本地 Ollama

示例：

```env
RAG_CHAT_MODEL_OPTIONS=tongyi:qwen-max|通义千问 qwen-max,ollama:qwen3.5:9b|Ollama qwen3.5:9b
```

### 文档切分和检索

| 变量 | 说明 |
| --- | --- |
| `RAG_CHUNK_SIZE` | 单个文本块大小 |
| `RAG_CHUNK_OVERLAP` | 文本块重叠长度 |
| `RAG_MAX_SPLIT_CHAR_NUM` | 超过该字符数才切分 |
| `RAG_RETRIEVAL_TOP_K` | 最终召回数量 |
| `RAG_RETRIEVAL_FETCH_K` | 初始候选召回数量 |
| `RAG_SIMILARITY_THRESHOLD_ENABLED` | 是否启用相似度阈值 |
| `RAG_SIMILARITY_THRESHOLD` | 相似度阈值 |
| `RAG_MMR_ENABLED` | 是否启用 MMR 多样性召回 |
| `RAG_QUERY_REWRITE_ENABLED` | 是否启用查询改写 |
| `RAG_RERANK_ENABLED` | 是否启用 LLM rerank |

调整切分或检索参数后，建议清空旧向量数据并重新导入知识库，否则旧分块会继续影响召回效果。

### 上传限制

| 变量 | 说明 |
| --- | --- |
| `RAG_UPLOAD_MAX_WORKERS` | 多文件上传并发数 |
| `RAG_MAX_UPLOAD_FILE_SIZE_MB` | 单文件最大体积 |
| `RAG_MAX_UPLOAD_BATCH_SIZE_MB` | 单批上传最大总体积 |
| `RAG_MAX_UPLOAD_BATCH_FILES` | 单批最多文件数 |

如果本地 Ollama 或 Chroma 较慢，可以把 `RAG_UPLOAD_MAX_WORKERS` 调小，例如 `1` 或 `2`。

## 常用命令

后端开发启动：

```bash
python app_api.py
```

前端开发启动：

```bash
cd frontend
pnpm dev
```

前端生产构建：

```bash
cd frontend
pnpm build
```

启动 Chroma：

```bash
docker compose -f docker-compose.chroma.yml up -d
```

停止 Chroma：

```bash
docker compose -f docker-compose.chroma.yml down
```

启动 Redis：

```bash
docker compose -f docker-compose.redis.yml up -d
```

停止 Redis：

```bash
docker compose -f docker-compose.redis.yml down
```

## 安全提醒

开源或部署前，请务必注意：

- 不要提交 `.env`
- 不要提交 `frontend/.env`
- 不要提交 `logs/`、`chroma_db/`、`frontend/dist/`、`frontend/node_modules/`
- 不要把 `DASHSCOPE_API_KEY`、`RAG_API_SECRET_KEY`、数据库密码、管理员密码写进代码
- 生产环境必须使用强密码和随机 JWT 密钥
- 生产环境不要使用默认管理员邮箱和密码
- 如果密钥曾经提交到公开仓库，请立刻吊销或轮换

本仓库保留 `.env.example` 和 `frontend/.env.example` 作为配置模板，真实配置应只放在本地或部署平台的环境变量中。

## 常见问题

### 后端启动时报 `请在 .env 中配置 RAG_API_SECRET_KEY`

说明 `.env` 里没有设置 JWT 密钥。生成一个随机值并写入：

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 后端启动时报 Redis 连接失败

确认 Redis 已启动：

```bash
docker compose -f docker-compose.redis.yml up -d
```

并检查 `.env`：

```env
RAG_REDIS_URL=redis://127.0.0.1:6379/0
```

### 上传文件时控制台出现 `Slow HTTP request`

这通常不是错误，而是上传、解析、embedding、写入 Chroma 的耗时超过了慢请求阈值。可以调大：

```env
RAG_LOG_SLOW_REQUEST_MS=10000
```

如果文件较大或本地模型较慢，也可以降低并发：

```env
RAG_UPLOAD_MAX_WORKERS=1
```

### DashScope 模型不可用

检查：

```env
DASHSCOPE_API_KEY=你的 API Key
RAG_USE_LOCAL_CHAT_MODEL=false
RAG_CHAT_MODEL=qwen-max
```

如果不想使用 DashScope，可以切换到 Ollama 本地模型：

```env
RAG_USE_LOCAL_CHAT_MODEL=true
RAG_LOCAL_MODEL=qwen3.5:9b
RAG_CHAT_MODEL_OPTIONS=ollama:qwen3.5:9b|Ollama qwen3.5:9b
```

### Ollama embedding 失败

确认 Ollama 服务正在运行，并且模型已经拉取：

```bash
ollama pull qwen3-embedding:latest
ollama list
```

检查 `.env`：

```env
RAG_OLLAMA_BASE_URL=http://localhost:11434
RAG_EMBEDDING_MODEL=qwen3-embedding:latest
```

### 前端请求 API 失败

确认后端运行在：

```text
http://127.0.0.1:8520
```

检查 `frontend/.env`：

```env
VITE_API_BASE_URL=/api
VITE_PROXY_TARGET=http://127.0.0.1:8520
```

然后重启前端开发服务器。

## 开发说明

- API 路由集中在 `rag_app/api/app.py`
- RAG 检索链在 `rag_app/services/rag_service.py`
- 知识库写入在 `rag_app/services/knowledge_base.py`
- 向量检索封装在 `rag_app/services/vector_store.py`
- 数据库模型在 `rag_app/storage/models.py`
- 配置统一在 `rag_app/config.py`
- 前端页面和组件集中在 `frontend/src/`

## License

请根据你的开源计划补充许可证文件，例如 MIT、Apache-2.0 或 GPL-3.0。
