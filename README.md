# 多租户加密货币交易执行与跟单平台

Multi-Tenant Crypto Trading & Copy Trading Platform V1.0.

当前阶段：GitHub + Docker Compose Mock 集成测试 + 第三阶段测试网准备。

本阶段默认只允许：

- SIMULATION 账户
- MockExchange
- 手动信号
- 受控风控配置
- Mock 下单和持仓更新

测试网能力处于受保护准备态：必须手动切换 `TESTNET`、显式开启测试网开关、启用账户和风控，并通过预检门禁后才允许测试网请求路径继续。禁止默认启用 TESTNET 或 REAL，禁止真实交易。

## 技术栈

- Frontend: Next.js, React, TypeScript
- Backend: FastAPI, Python 3.12+
- Database: PostgreSQL
- Cache: Redis
- ORM: SQLAlchemy
- Migration: Alembic
- Tests: pytest
- Lint: Ruff
- Containers: Docker, Docker Compose
- CI: GitHub Actions

## 目录

```text
backend/                         FastAPI 后端
frontend/                        Next.js 前端
docs/                            阶段设计与集成测试说明
scripts/integration/             Mock API 集成测试脚本
.github/workflows/               CI 与 Docker Integration
docker-compose.yml
.env.example
```

## 本地或 Ubuntu 启动

复制环境变量文件：

```bash
cp .env.example .env
```

启动开发服务：

```bash
docker compose up --build -d postgres redis backend frontend
```

访问：

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/api/v1/health
- Backend dependency health: http://localhost:8000/api/v1/health/dependencies
- Backend docs: http://localhost:8000/docs

Ubuntu + Tailscale 部署说明见：

- `docs/ubuntu-docker-integration.md`

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

Docker Mock 集成：

```bash
docker compose build
docker compose up --detach postgres redis backend
docker compose run --rm integration-test
python scripts/integration/mock_compose_check.py
docker compose down --remove-orphans
```

## 当前已完成

基础架构：

- FastAPI 基础项目
- Next.js 基础项目
- Docker Compose
- PostgreSQL
- Redis
- Alembic 初始迁移
- `.env.example`
- README
- GitHub Actions
- pytest
- Ruff

业务能力：

- 用户注册与登录
- JWT 鉴权
- 密码哈希存储
- user_id UUID
- email UNIQUE
- username UNIQUE
- 用户角色：admin / normal_user，预留 team_admin
- 授权共享机制
- API Key 元数据管理
- API Secret 加密保存
- API Secret 不返回前端
- 账户模式：SIMULATION / TESTNET / REAL
- MockExchange
- Manual Signal Engine
- Risk Engine
- Position Engine
- Order Engine
- Order State Machine
- 幂等执行：同一个 `signal_id + exchange_account_id` 只能执行一次
- 受控风控配置接口，仅允许 SIMULATION 账户修改
- Binance / Bybit / OKX 测试网适配骨架，默认关闭
- 测试网只读请求结构、签名请求准备、测试网订单预检门禁
- 测试网订单请求准备与受限执行服务
- 测试网用户流连接计划与注入式运行时 shell
- Rate Limit Service，支持内存计数与 Redis 计数后端
- Position Reconciliation Service，支持快照差异检测
- Reconciliation Worker，支持注入式快照 provider 和持久化编排
- Audit / System Event / Internal Notification 持久化边界
- Notification Service，支持内部通知写入、读取和标记已读

测试覆盖：

- Backend Ruff + pytest
- Frontend build
- Docker Compose 启动链路
- PostgreSQL / Redis health check
- Mock API 全链路测试
- 数据持久化读取
- 多租户隔离
- API Secret 不回显
- 默认风控拒单
- 风控启用后 Mock FILLED
- Position delta execution
- 幂等机制不能绕过租户隔离
- 测试网预检门禁、签名请求、运行时限频
- 对账 drift 检测、审计/事件/内部通知持久化
- 内部通知读取和已读状态的 `user_id` 隔离

## 安全原则

- 账户模式必须区分 SIMULATION、TESTNET、REAL。
- 默认阶段禁止真实交易。
- API Secret 必须加密存储，不返回前端，不写日志。
- 所有业务查询必须基于 `user_id` 做租户隔离。
- 幂等检查不能绕过租户隔离。
- 风控默认拒单，必须显式启用。
- 当前 V1 只允许 SIMULATION 账户通过 API 修改风控设置。
- 测试网订单路径必须通过账户模式、全局开关、账户交易开关、风控开关、手动确认和限频检查。
- Audit Log 必须 append-only。

## 禁止命令

在本项目中不要使用以下命令，除非已经有明确备份与恢复计划：

```bash
docker system prune
docker volume prune
docker network prune
docker compose down -v
```

这些命令可能删除数据、网络、缓存或命名卷。资金系统中的数据丢失会影响审计、对账与事故分析。

## 当前限制

- 未接入真实交易所生产环境。
- 测试网适配仍是受保护准备态，默认不发送测试网订单。
- 未启用生产级 HTTPS、监控、告警、备份、日志轮转。
- 真实 WebSocket transport、连续事件消费、余额/持仓同步写入尚未实现。
- Telegram / Email / Webhook 外部通知发送尚未实现。
- 自动对账修复尚未实现。
