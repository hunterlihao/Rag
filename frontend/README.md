# frontend

这是当前 RAG 项目的独立前端，技术栈为 Vue 3 + Vite + Element Plus。

## 功能

- 登录 / 注册
- 路由守卫
- 问答主页 + 独立知识库页面
- 会话历史、问答区、知识文件上传、进度显示
- 已接入真实 Python 后端 API

## 启动

```powershell
cd D:\code\python-code\AIDemo\RAG\frontend
pnpm install
pnpm dev
```

生产构建：

```powershell
pnpm build
```

## 环境变量

复制一份 `.env.example` 为 `.env`，按需修改：

- `VITE_USE_MOCK_API=false`：默认走真实后端
- `VITE_API_BASE_URL=/api`
- `VITE_PROXY_TARGET=http://127.0.0.1:8000`：Vite 开发服务把 `/api` 代理到本地 FastAPI
- `VITE_CHAT_MODEL`：页面上展示的聊天模型名
- `VITE_EMBEDDING_MODEL`：页面上展示的向量模型名
- `VITE_UPLOAD_CONCURRENCY`：前端同时上传几个文件
- `VITE_ALLOWED_HOSTS`：允许通过哪些域名访问 Vite 开发服务，支持内网穿透域名

## 真实模型切换

前端这里只负责展示。真正切换当前 Python RAG 后端所用本地模型，还是改项目根目录：

- `D:\code\python-code\AIDemo\RAG\.env` 里的 `RAG_LOCAL_MODEL`
- `D:\code\python-code\AIDemo\RAG\.env` 里的 `RAG_USE_LOCAL_CHAT_MODEL`
