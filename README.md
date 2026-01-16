# Healthy RAG - 健康问答系统

基于 RAG（检索增强生成）的智能健康问答系统，通过多轮对话收集用户健康信息，生成个性化健康报告。

## 技术栈

### 后端
- **FastAPI**: 现代化的 Python Web 框架
- **SQLAlchemy**: ORM 数据库操作
- **SQLite**: 轻量级数据库
- **JWT**: 用户认证
- **OpenAI API**: 大语言模型集成

### 前端
- **Vue 3**: 渐进式 JavaScript 框架
- **Vite**: 现代化前端构建工具
- **Element Plus**: UI 组件库
- **Axios**: HTTP 客户端

## 项目结构

```
healthy-rag/
├── src/                      # 后端源码
│   ├── api/                  # API 路由
│   │   ├── routers/          # 路由模块
│   │   └── dependencies.py   # 依赖注入
│   ├── services/             # 业务逻辑层
│   │   ├── business_service.py  # 核心业务逻辑
│   │   └── llm_service.py       # LLM 服务
│   ├── models/               # 数据模型
│   ├── schemas/              # Pydantic 模型
│   ├── config/               # 配置
│   ├── utils/                # 工具函数
│   └── main.py               # 应用入口
├── frontend/                 # 前端源码
│   ├── src/
│   │   ├── views/            # 页面组件
│   │   ├── router/           # 路由配置
│   │   ├── stores/           # 状态管理
│   │   └── utils/            # 工具函数
│   └── package.json
├── scripts/                  # 脚本文件
├── tests/                    # 测试文件
├── requirements.txt          # Python 依赖
└── README.md                 # 项目说明
```

## 快速开始

### 1. 环境准备

**系统要求：**
- Python 3.9+
- Node.js 16+
- npm 或 yarn

### 2. 后端启动

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
source venv/bin/activate  # macOS/Linux
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 启动后端服务
uvicorn src.main:app --reload --host 0.0.0.0 --port 8010
```

后端服务将运行在: http://localhost:8010
API 文档: http://localhost:8010/docs

### 3. 前端启动

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将运行在: http://localhost:3001

### 4. 快速重启

使用提供的脚本快速重启服务：

```bash
# 重启后端
./restart_backend.sh

# 或手动重启前后端
pkill -f uvicorn && pkill -f vite
uvicorn src.main:app --reload --host 0.0.0.0 --port 8010 > backend.log 2>&1 &
cd frontend && npm run dev > frontend.log 2>&1 &
```

## 主要功能

### 1. 用户认证
- 用户注册/登录
- JWT Token 认证
- 24小时 Token 有效期

### 2. 智能对话
- 多轮对话收集健康信息
- 基于 LLM 的智能问答
- 实时消息流式响应
- 对话历史记录

### 3. 健康报告
- 自动生成个性化健康报告
- 风险评估和建议
- 产品推荐
- 报告历史查看

### 4. 用户界面
- 现代化的聊天界面
- 可折叠侧边栏
- 历史对话管理
- 响应式设计

## 配置说明

### 环境变量

创建 `.env` 文件配置以下参数：

```env
# 数据库配置
DATABASE_URL=sqlite+aiosqlite:///./healthy.db

# JWT 配置
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# OpenAI API 配置
OPENAI_API_KEY=your-openai-api-key
OPENAI_API_BASE=https://api.openai.com/v1
```

## API 文档

启动后端服务后，访问以下地址查看完整 API 文档：

- Swagger UI: http://localhost:8010/docs
- ReDoc: http://localhost:8010/redoc

## 开发规范

项目遵循企业级 Python 开发规范，包括：

- PEP 8 代码风格
- 类型提示
- 分层架构（API层、服务层、数据层）
- 依赖注入
- 异步编程
- 错误处理和日志记录
- 数据验证

详见项目根目录的开发规范文档。

## 测试

```bash
# 运行测试
pytest tests/

# 运行特定测试
pytest tests/test_api.py

# 生成覆盖率报告
pytest --cov=src tests/
```

## 部署

### 生产环境部署

1. 构建前端：
```bash
cd frontend
npm run build
```

2. 配置生产环境变量

3. 使用 Gunicorn + Uvicorn 运行后端：
```bash
gunicorn src.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8010
```

4. 使用 Nginx 作为反向代理

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue。

