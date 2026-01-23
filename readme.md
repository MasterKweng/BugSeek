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

### 前端
- React 18 - UI 框架
- TypeScript - 类型安全
- Ant Design 5 - UI 组件库
- Vite - 构建工具
- Zustand - 状态管理
- React Router - 路由管理

## 快速开始

### 1. 启动 PostgreSQL 数据库

```bash
# 使用 Docker 启动 PostgreSQL
docker run -d \
  --name bugseek-postgres \
  -e POSTGRES_DB=bugseek \
  -e POSTGRES_USER=bugseek \
  -e POSTGRES_PASSWORD=bugseek \
  -p 5432:5432 \
  postgres:15
```
docker run -d \
     --name bugseek-postgres \
     -e POSTGRES_DB=bugseek \
     -e POSTGRES_USER=bugseek \
     -e POSTGRES_PASSWORD=bugseek \
     -p 0.0.0.0:5432:5432 \
     postgres:15

### 2. 启动后端服务

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

### 3. 启动前端服务

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

前端服务将在 http://localhost:3000 启动

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

### 待实现

- 测试脚本自动生成
- 智能场景组装
- Mock 服务管理
- 测试套件管理
- 测试执行引擎
- 测试报告生成
- CI/CD 集成
- 精准测试（TIA）
- 质量门禁

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