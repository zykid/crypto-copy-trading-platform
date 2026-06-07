# 多租户加密货币交易执行与跟单平台

V1.0 第一阶段开发环境骨架。

当前阶段只允许本地开发、Mock Exchange 和模拟模式。禁止真实交易。

## 技术栈

- Frontend: Next.js, React, TypeScript
- Backend: FastAPI, Python 3.12+
- Database: PostgreSQL
- Cache: Redis
- ORM: SQLAlchemy
- Migration: Alembic, 后续阶段接入
- Tests: pytest, 后续阶段配置
- Lint: Ruff, 后续阶段配置
- Containers: Docker, Docker Compose

## 目录

```text
backend/      FastAPI 后端
frontend/     Next.js 前端
docker-compose.yml
.env.example
```

## 本地启动

复制环境变量文件：

```bash
cp .env.example .env
```

启动开发服务：

```bash
docker compose up --build
```

访问：

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/api/v1/health
- Backend docs: http://localhost:8000/docs

## 开发检查

后端：

```bash
cd backend
python -m pip install -e ".[dev]"
ruff check .
pytest
```

前端：

```bash
cd frontend
npm install
npm run build
```

## 安全原则

- 账户模式必须区分 SIMULATION、TESTNET、REAL。
- 默认阶段禁止真实交易。
- API Secret 必须加密存储，不返回前端，不写日志。
- 所有业务查询必须基于 user_id 做租户隔离。
- Audit Log 必须 append-only。

## 当前完成范围

- FastAPI 基础项目
- Next.js 基础项目
- Docker Compose
- PostgreSQL
- Redis
- `.env.example`
- README

第三步已配置：

- GitHub Actions
- pytest
- Ruff

下一步确认后再实现用户系统、授权系统和 API Key 管理。
