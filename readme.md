# BugSeek

BugSeek 是一个 AI 驱动的测试质量平台，提供从需求洞察到 CI/CD 集成的全流程测试解决方案。

## 项目结构

```
BugSeek/
├── backend/           # 后端项目（FastAPI + Python）
├── frontend/          # 前端项目（React + TypeScript + Ant Design）
└── README.md
```

## 技术栈

### 后端
- FastAPI - Web 框架
- PostgreSQL - 数据库
- SQLAlchemy - ORM
- JWT - 认证
- prance - OpenAPI 文档解析
- Celery - 异步任务队列
- Redis - 消息队列和缓存
- Docker - 容器化部署

### 前端
- React 18 - UI 框架
- TypeScript - 类型安全
- Ant Design 5 - UI 组件库
- Vite - 构建工具
- Zustand - 状态管理
- React Router - 路由管理

## 快速开始

### 前提条件

- Docker 和 Docker Compose 已安装
- Python 3.10+
- Node.js 18+

### 1. 启动 PostgreSQL 数据库（如果未启动）

```bash
# 使用 Docker 启动 PostgreSQL
docker run -d \
  --name bugseek-postgres \
  -e POSTGRES_DB=bugseek \
  -e POSTGRES_USER=bugseek \
  -e POSTGRES_PASSWORD=bugseek \
  -p 0.0.0.0:5432:5432 \
  postgres:15
```

### 2. 启动 Redis（如果未启动）

```bash
# 使用 Docker 启动 Redis（端口 6380，与其他项目的 Redis 分开，避免冲突）
docker run -d \
  --name bugseek-redis \
  -p 0.0.0.0:6380:6380 \
  redis:7.0 \
  redis-server --port 6380
```

**说明**: Redis 使用端口 6380（映射到容器内的 6379），与其他项目的 Redis（如 6379）分开，避免冲突。

### 3. 启动 Celery Worker

```bash
cd backend

# 使用命令行启动 Celery Worker
celery -A app.celery_config worker --loglevel=info --pool=solo
```

**说明**: Celery Worker 会连接到 Redis（端口 6380）作为消息队列，处理异步任务。

**参数说明**:
- `-A app.celery_config`: 指定 Celery 应用配置模块
- `worker`: 启动 worker 进程
- `--loglevel=info`: 日志级别为 info
- `--pool=solo`: 使用 solo 池（单进程，适合开发环境）

### 4. 启动后端服务

```bash
cd backend

# 创建虚拟环境（可选）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库连接等信息

# 初始化数据库
python -c "from app.db.session import init_db; init_db()"

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端服务将在 http://localhost:8000 启动

API 文档：http://localhost:8000/docs

### 5. 启动前端服务

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将在 http://localhost:3000 启动

## 服务管理

### 查看服务状态

```bash
# 查看 Docker 容器状态
docker ps

# 查看 Redis 日志
docker logs -f bugseek-redis

# 查看 PostgreSQL 日志
docker logs -f bugseek-postgres
```

### 停止服务

```bash
# 停止 Redis
docker stop bugseek-redis
docker rm bugseek-redis

# 停止 PostgreSQL
docker stop bugseek-postgres
docker rm bugseek-postgres

# 停止 Celery Worker（按 Ctrl+C）
```

### 重启服务

```bash
# 重启 Redis
docker restart bugseek-redis

# 重启 PostgreSQL
docker restart bugseek-postgres

# 重启 Celery Worker
# 先停止（按 Ctrl+C），然后重新执行启动命令：
cd backend
celery -A app.celery_config worker --loglevel=info --pool=solo
```

## 功能模块

### 已实现

#### 登录注册模块
- 用户注册
- 用户登录
- 获取用户信息
- 修改密码
- 更新用户信息
- 用户登出

#### 接口文档管理模块
- 导入接口文档（Swagger/OpenAPI）
- 文档列表展示
- 文档详情查看
- 删除文档

#### 接口定义管理模块
- 接口列表展示
- 接口详情查看
- 接口搜索
- 接口过滤（按方法）

#### 智能场景组装模块
- 接口依赖分析（基于分组的异步分析）
- 业务链路识别
- 场景自动生成
- 场景依赖图可视化
- 场景执行（支持变量传递）

### 待实现

- 测试脚本自动生成
- Mock 服务管理
- 测试套件管理
- 测试报告生成
- CI/CD 集成
- 精准测试（TIA）
- 质量门禁

## Docker 服务说明

### 服务架构

BugSeek 使用 Docker 管理以下服务：

| 服务 | 容器名 | 端口 | 用途 |
|------|--------|------|------|
| PostgreSQL | bugseek-postgres | 5432:5432 | 主数据库 |
| Redis | bugseek-redis | 6380:6379 | Celery 任务队列 |

**Celery Worker** 通过命令行直接运行（不使用 Docker）

### 端口说明

- **5432**: PostgreSQL 数据库
- **6380**: BugSeek Redis（映射到容器内的 6379，与其他项目的 Redis 分开，避免冲突）
- **8000**: FastAPI 后端服务
- **3000**: 前端服务

### 常用命令

```bash
# 启动 Redis
docker start bugseek-redis

# 停止 Redis
docker stop bugseek-redis

# 启动 PostgreSQL
docker start bugseek-postgres

# 停止 PostgreSQL
docker stop bugseek-postgres

# 查看 Redis 日志
docker logs -f bugseek-redis

# 查看 PostgreSQL 日志
docker logs -f bugseek-postgres

# 进入 Redis 容器
docker exec -it bugseek-redis redis-cli

# 进入 PostgreSQL 容器
docker exec -it bugseek-postgres psql -U bugseek -d bugseek
```

## 开发说明

### 后端开发

- API 路由定义在 `backend/app/api/v1/` 目录下
- 数据模型定义在 `backend/app/db/base.py`
- 配置文件：`backend/app/config.py`
- 依赖注入：`backend/app/dependencies.py`

### 前端开发

- 页面组件：`frontend/src/pages/`
- 通用组件：`frontend/src/components/`
- 状态管理：`frontend/src/store/`
- API 服务：`frontend/src/services/`
- 类型定义：`frontend/src/types/`

## 环境变量

### 后端环境变量（.env）

```bash
# 数据库配置
DATABASE_URL=postgresql://bugseek:bugseek@localhost:5432/bugseek

# JWT 配置
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Redis 配置（用于 Celery 异步任务队列，端口 6380）
REDIS_URL=redis://localhost:6380/0

# 文件上传配置
UPLOAD_DIR=./uploads
MAX_UPLOAD_SIZE=10485760

# 日志配置
LOG_DIR=./logs
```

### 前端环境变量（.env）

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## 许可证

MIT