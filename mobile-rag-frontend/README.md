# mobile-rag-frontend

标准 **Vue 3 + TypeScript（H5-only）** 移动端前端，用于替代现有 uni-app 方案。

## 开发

### 1) 配置 API Base

在开发环境建议使用本地后端（默认 `http://localhost:8010/api/v1`）。你也可以通过环境变量覆盖：

创建 `mobile-rag-frontend/.env.local`：

```bash
VITE_API_BASE_URL=http://localhost:8010/api/v1
```

生产环境通常走相对路径（由 Nginx 反代）：

```bash
VITE_API_BASE_URL=/api/v1
```

### 2) 安装与启动

```bash
cd mobile-rag-frontend
npm install
npm run dev
```

### 3) 构建

```bash
npm run build
```

## 页面路由

- `/login`：登录
- `/register`：注册（邮箱验证码）
- `/chat`：问诊
- `/reports`：报告列表
- `/report/:session_id`：报告详情（iframe 展示后端 HTML）
- `/me`：我的

## 与后端的契约（核心）

- **登录**：`POST /api/v1/auth/login`，`application/x-www-form-urlencoded`
- **API 鉴权**：`Authorization: Bearer <token>`
- **报告 HTML**：iframe 加载 `GET /api/v1/report/{session_id}/html?token=<token>`

## 旧工程处理（当前策略）

- `mobile-frontend`、`mobile-rag-v1` 进入冻结状态（只修阻塞性 bug，不新增需求）。
- 新工程稳定后再决定归档/删除旧目录。

# Vue 3 + TypeScript + Vite

This template should help get you started developing with Vue 3 and TypeScript in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about the recommended Project Setup and IDE Support in the [Vue Docs TypeScript Guide](https://vuejs.org/guide/typescript/overview.html#project-setup).
