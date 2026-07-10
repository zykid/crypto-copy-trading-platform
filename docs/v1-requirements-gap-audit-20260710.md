# V1 初始需求缺口审计（2026-07-10）

本审计将最初的 V1 要求与当前代码仓库逐项对照。它是代码级检查，不构成真实交易授权。

## 当前安全定位

当前版本适合：

- 通过 `MockExchange` 执行 SIMULATION 模拟订单。
- 通过独立 TESTNET API 路径进行测试网订单窗口验证。
- 在交易所凭证和网络允许时，执行 TESTNET / REAL 只读认证、余额和持仓读取。
- 验证操作员流程、审计、备份、恢复演练和部署状态。

当前版本**尚不能提交 REAL 真实订单**。非 Mock 交易所适配器仍为只读实现，后端也没有
REAL 订单提交 API。

## 已实现基线

| 初始要求 | 状态 | 代码现状 |
| --- | --- | --- |
| FastAPI、Next.js、PostgreSQL、Redis、SQLAlchemy、Alembic | 已实现 | 仓库及 Compose 服务完整。 |
| 邮箱/用户名/密码用户和 UUID 身份 | 已实现 | 用户模型、注册、登录、JWT 和唯一约束已存在。 |
| 角色与授权共享权限 | 基线已实现 | 已有 `super_admin`、`admin`、`normal_user`、`team_admin` 及权限字段/API。 |
| 多租户归属检查 | 基线已实现 | 账户、信号、风控、持仓和订单核心查询绑定 `user_id`。 |
| API Secret 加密保存 | 已实现 | 密钥加密、敏感操作重新认证、前端不返回明文。 |
| SIMULATION / TESTNET / REAL 账户模式 | 已实现 | 账户级枚举、API 和 UI 已存在。 |
| manual Signal Engine | 已实现 | 手工信号 API 与持久化已存在。 |
| Position Engine 仓位差额 | 已实现 | 目标仓位减当前仓位用于计算执行数量。 |
| Mock 订单执行 | 已实现 | 包含风控、幂等、Mock 下单和成交持久化。 |
| 幂等机制 | 基线已实现 | `signal_id + exchange_account_id` 唯一，执行 ID 和客户端订单 ID 唯一。 |
| 订单状态定义 | 模型已实现 | `OrderExecutionStatus` 包含全部要求状态。 |
| Rate Limit Service | 基线已实现 | 已有 Redis 运行时限频和交易所规则配置。 |
| Position Reconciliation | 基线已实现 | 已有比较、持久化、告警、Worker 和修复建议模块。 |
| Audit Log Append Only | 已实现 | PostgreSQL 触发器禁止 UPDATE / DELETE。 |
| Notification Service | 基线已实现 | 已有内部通知和偏好 API。 |
| 备份、恢复演练、日志轮转 | 基线已实现 | 已有 `pg_dump`、校验、定时器模板和 Docker 日志上限。 |
| CI 与 Docker Integration | 已实现 | GitHub Actions 工作流已存在。 |

## 部分实现

| 初始要求 | 当前限制 | 完成条件 |
| --- | --- | --- |
| 统一 Risk Engine | 已检查数量、禁用币种和单笔金额；最大仓位、最大杠杆字段尚未真正执行，每日亏损未实现。 | 增加组合仓位/杠杆检查、每日已实现盈亏限额、测试和详细审计。 |
| Kill Switch | 关闭账户风控会发送 Emergency Stop 告警，但没有持久化的全局 Kill Switch 状态/API。 | 增加全局状态、超级管理员 API/UI、所有订单入口 fail-closed 检查和集成测试。 |
| Order State Machine | 状态枚举完整，但 Mock 执行主要直接进入 FILLED/FAILED，没有交易所事件驱动的统一状态转换器。 | 增加状态转换校验、转换历史、部分成交、撤单、超时与对账处理。 |
| Exchange Adapter | 已有公开和私有只读请求；生产适配器未实现 `get_open_orders`、`get_order_status`、`place_order`、`cancel_order`。 | 按交易所实现签名请求、标准化错误和完整测试。 |
| WebSocket 优先 | 已有部分测试网私有用户流组件，但订单、余额、持仓和行情尚未全部由 WebSocket 驱动。 | 增加受监管连接、断线恢复、缺口补数、REST 对账和健康状态。 |
| Position Reconciliation 调度 | Worker 和只读修复建议存在；生产调度与自动修复未开启。 | 增加调度所有权、租约、指标和单独审批的修复执行器。 |
| Notification Service | 内部通知和受保护的外部发送器存在；真实 Telegram/Email/Webhook 目标仍默认关闭。 | 配置并验证真实目标，且不发送敏感字段。 |
| 团队账户管理 | 已有角色和权限基础，但团队生命周期和正式 UI 不完整。 | 增加团队所有权、成员、邀请和租户安全管理。 |
| 生产运维 | 已有生产 Compose、Caddy 和监控骨架。 | 在最终主机完成 HTTPS/私网访问、告警、备份定时器、恢复演练和看板。 |

## 尚未实现的 V1 功能块

1. 缺少 `copy_trading_rules` 持久化和完整跟单规则 API。
2. 缺少 `same_quantity`、`fixed_quantity`、`fixed_notional`、`equity_ratio`、
   `multiplier` 的跟单计算与多账户分发执行。
3. 缺少生产 REAL 订单提交 API 和真实交易所订单执行器。
4. 缺少能同时阻断 manual、copy、strategy、webhook、AI 的持久化全局 Emergency Stop。
5. 正式行情图、订单簿、账户权益、活动订单和成交历史尚未由完整交易所实时数据流支持。

## REAL 交易发布阻塞项

以下项目全部通过前，REAL 交易必须保持关闭：

1. 实现生产适配器的下单、撤单、订单状态和活动订单查询。
2. 实现专用 REAL 订单 API，禁止复用 Mock 执行接口。
3. 强制执行账户模式、账户交易开关、风控开关、全局 Kill Switch、用户权限、
   MFA/重新认证和有时效的订单窗口审批。
4. 强制执行币种规则、数量、金额、仓位、杠杆和每日亏损限制。
5. 持久化并校验每次订单状态转换和交易所响应。
6. 在数据库唯一约束之外增加 Redis 幂等锁。
7. 验证 WebSocket 订单更新、REST 对账和超时处理。
8. 增加拒绝、重试、重复、部分成交、撤单、超时、交易所故障和限频失败的端到端测试。
9. 完成带日期的小额资金清单，并对一笔精确订单单独人工批准。

## 建议交付顺序

1. 稳定认证和受保护页面跳转。
2. 增加持久化全局 Kill Switch，并补齐 Risk Engine 强制检查。
3. 先在 TESTNET 完成一个交易所的完整订单生命周期和 WebSocket 流。
4. 在 SIMULATION 模式完成跟单规则持久化和计算。
5. 完整执行 TESTNET 下单、失败、限频和对账演练。
6. 在环境级硬禁用开关后实现 REAL 执行器。
7. 通过独立批准的小额资金订单窗口执行首笔测试。

