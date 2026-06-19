"use client";

import { useEffect, useMemo, useState } from "react";

type ApiResult = Record<string, unknown> | Record<string, unknown>[] | null;

type LogEntry = {
  label: string;
  ok: boolean;
  detail: string;
};

type SessionState = {
  token: string;
  userId: string;
  username: string;
  role: string;
  accountId: string;
  signalId: string;
  executionId: string;
};

type StorageLocation = {
  id: string;
  label: string;
  path: string;
  is_current: boolean;
};

const emptySession: SessionState = {
  token: "",
  userId: "",
  username: "",
  role: "",
  accountId: "",
  signalId: "",
  executionId: "",
};

function resolveApiBase() {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
  if (typeof window === "undefined") {
    return configured || "http://localhost:8000";
  }
  if (!configured || configured === "http://localhost:8000") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return configured;
}

function formatDetail(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "完成";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}

export default function Home() {
  const [apiBase, setApiBase] = useState("http://localhost:8000");
  const [session, setSession] = useState<SessionState>(emptySession);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [storageLocations, setStorageLocations] = useState<StorageLocation[]>([]);
  const [busy, setBusy] = useState(false);
  const [manualLogin, setManualLogin] = useState({
    usernameOrEmail: "",
    password: "",
  });

  useEffect(() => {
    setApiBase(resolveApiBase());
  }, []);

  const apiRoot = useMemo(() => `${apiBase}/api/v1`, [apiBase]);

  function appendLog(label: string, ok: boolean, detail: unknown) {
    setLogs((current) => [
      { label, ok, detail: formatDetail(detail) },
      ...current.slice(0, 11),
    ]);
  }

  async function apiRequest(
    method: string,
    path: string,
    payload?: Record<string, unknown>,
    token = session.token,
    expectedStatus = 200,
  ): Promise<ApiResult> {
    const response = await fetch(`${apiRoot}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(payload ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: payload ? JSON.stringify(payload) : undefined,
    });
    const text = await response.text();
    const body = text ? JSON.parse(text) : null;
    if (response.status !== expectedStatus) {
      throw new Error(`${method} ${path} 返回 ${response.status}: ${formatDetail(body)}`);
    }
    return body;
  }

  function requireObject(result: ApiResult, label: string) {
    if (result === null || Array.isArray(result)) {
      throw new Error(`${label} 返回格式异常`);
    }
    return result;
  }

  async function runStep(label: string, action: () => Promise<unknown>) {
    setBusy(true);
    try {
      const result = await action();
      appendLog(label, true, result);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      appendLog(label, false, message);
      throw error;
    } finally {
      setBusy(false);
    }
  }

  async function checkHealth() {
    await runStep("健康检查", async () => {
      const health = await apiRequest("GET", "/health", undefined, "");
      const dependencies = await apiRequest("GET", "/health/dependencies", undefined, "");
      return { health, dependencies };
    });
  }

  async function loadAuthenticatedSession(
    token: string,
  ): Promise<Record<string, unknown>> {
    const profile = requireObject(
      await apiRequest("GET", "/users/me", undefined, token),
      "用户资料",
    );
    const role = String(profile.role);
    let locations: StorageLocation[] = [];

    if (role === "super_admin") {
      const result = await apiRequest(
        "GET",
        "/admin/storage/locations",
        undefined,
        token,
      );
      if (!Array.isArray(result)) {
        throw new Error("存储位置返回格式异常");
      }
      locations = result as StorageLocation[];
    }

    setSession((current) => ({
      ...current,
      token,
      userId: String(profile.id),
      username: String(profile.username),
      role,
    }));
    setStorageLocations(locations);
    return profile;
  }

  async function refreshStorageLocations() {
    await runStep("刷新存储位置", async () => {
      const result = await apiRequest("GET", "/admin/storage/locations");
      if (!Array.isArray(result)) {
        throw new Error("存储位置返回格式异常");
      }
      const locations = result as StorageLocation[];
      setStorageLocations(locations);
      return locations;
    });
  }

  async function registerAndLogin() {
    await runStep("注册并登录测试用户", async () => {
      const suffix = Date.now().toString();
      const username = `ui_user_${suffix}`;
      const password = "ChangeMe12345!";
      const user = requireObject(
        await apiRequest(
          "POST",
          "/auth/register",
          {
            email: `ui_${suffix}@example.com`,
            username,
            password,
          },
          "",
          201,
        ),
        "注册",
      );
      const tokenResponse = requireObject(
        await apiRequest(
          "POST",
          "/auth/login",
          { username_or_email: username, password },
          "",
        ),
        "登录",
      );
      const profile = await loadAuthenticatedSession(
        String(tokenResponse.access_token),
      );
      return { user_id: profile.id, username: profile.username };
    });
  }

  async function loginExisting() {
    await runStep("登录已有用户", async () => {
      const tokenResponse = requireObject(
        await apiRequest(
          "POST",
          "/auth/login",
          {
            username_or_email: manualLogin.usernameOrEmail,
            password: manualLogin.password,
          },
          "",
        ),
        "登录",
      );
      const profile = await loadAuthenticatedSession(
        String(tokenResponse.access_token),
      );
      return {
        username: profile.username,
        user_id: profile.id,
        role: profile.role,
        token_loaded: true,
      };
    });
  }

  async function createMockAccount() {
    await runStep("创建 Mock 模拟账户", async () => {
      const account = requireObject(
        await apiRequest("POST", "/exchange-accounts", {
          exchange_name: "mock",
          account_label: "UI Mock Simulation",
          account_mode: "SIMULATION",
          trading_enabled: true,
        }),
        "创建账户",
      );
      const accountId = String(account.id);
      setSession((current) => ({ ...current, accountId }));
      return { account_id: accountId, mode: account.account_mode };
    });
  }

  async function configureMockKey() {
    await runStep("写入模拟 API Key 元数据", async () => {
      const metadata = await apiRequest(
        "POST",
        `/exchange-accounts/${session.accountId}/api-key`,
        {
          api_key: "mock-key-ui",
          api_secret: "mock-secret-never-display",
          passphrase: "mock-passphrase",
        },
      );
      return metadata;
    });
  }

  async function enableRisk() {
    await runStep("开启模拟风控交易", async () => {
      return apiRequest("PATCH", `/risk-settings/${session.accountId}`, {
        trading_enabled: true,
        min_order_quantity: "0.01",
        max_order_quantity: "1",
        max_single_order_notional: "1000",
      });
    });
  }

  async function previewTarget() {
    await runStep("仓位差额预览", async () => {
      return apiRequest(
        "POST",
        `/positions/${session.accountId}/target-preview?symbol=BTCUSDT&target_quantity=0.5`,
      );
    });
  }

  async function executeManualOrder() {
    await runStep("执行手工 Mock 订单", async () => {
      const signal = requireObject(
        await apiRequest(
          "POST",
          "/signals/manual",
          { symbol: "BTCUSDT", side: "BUY", order_type: "MARKET", quantity: "0.2" },
          session.token,
          201,
        ),
        "创建信号",
      );
      const execution = requireObject(
        await apiRequest("POST", `/orders/execute-signal/${signal.id}`, {
          exchange_account_id: session.accountId,
        }),
        "执行订单",
      );
      setSession((current) => ({
        ...current,
        signalId: String(signal.id),
        executionId: String(execution.execution_id),
      }));
      return execution;
    });
  }

  async function verifyIdempotency() {
    await runStep("幂等重复执行校验", async () => {
      const duplicate = requireObject(
        await apiRequest("POST", `/orders/execute-signal/${session.signalId}`, {
          exchange_account_id: session.accountId,
        }),
        "重复执行",
      );
      return {
        original_execution_id: session.executionId,
        duplicate_execution_id: duplicate.execution_id,
        same_execution: duplicate.execution_id === session.executionId,
      };
    });
  }

  async function runFullMockFlow() {
    setBusy(true);
    try {
      await checkHealth();
      await registerAndLogin();
      await createMockAccount();
      await configureMockKey();
      await enableRisk();
      await previewTarget();
      await executeManualOrder();
      await verifyIdempotency();
    } finally {
      setBusy(false);
    }
  }

  const canUseAccount = Boolean(session.token && session.accountId);
  const canVerifyIdempotency = Boolean(canUseAccount && session.signalId);

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <div className="brand">多租户加密货币交易执行与跟单平台</div>
          <div className="subtle">Ubuntu 集成测试控制台</div>
        </div>
        <div className="status">SIMULATION ONLY</div>
      </header>

      <div className="main console-layout">
        <section className="panel hero-panel">
          <div>
            <h1>开发环境操作台</h1>
            <p>
              当前页面只走 MockExchange 与 SIMULATION 模式，用于验证登录、租户隔离、风控、仓位差额、订单状态机和幂等执行。
            </p>
          </div>
          <div className="api-chip">API {apiRoot}</div>
        </section>

        <section className="panel controls-panel">
          <div className="panel-heading">
            <h2>快速流程</h2>
            <span>不会发送真实交易所订单</span>
          </div>
          <div className="button-grid">
            <button onClick={checkHealth} disabled={busy}>健康检查</button>
            <button onClick={registerAndLogin} disabled={busy}>注册测试用户</button>
            <button onClick={createMockAccount} disabled={busy || !session.token}>创建 Mock 账户</button>
            <button onClick={configureMockKey} disabled={busy || !canUseAccount}>配置模拟 Key</button>
            <button onClick={enableRisk} disabled={busy || !canUseAccount}>开启风控交易</button>
            <button onClick={previewTarget} disabled={busy || !canUseAccount}>仓位预览</button>
            <button onClick={executeManualOrder} disabled={busy || !canUseAccount}>执行订单</button>
            <button onClick={verifyIdempotency} disabled={busy || !canVerifyIdempotency}>幂等校验</button>
          </div>
          <button className="primary-action" onClick={runFullMockFlow} disabled={busy}>
            一键运行 Mock 全链路
          </button>
        </section>

        <section className="panel state-panel">
          <div className="panel-heading">
            <h2>会话状态</h2>
            <span>{busy ? "运行中" : "待命"}</span>
          </div>
          <dl className="state-list">
            <div><dt>用户</dt><dd>{session.username || "未登录"}</dd></div>
            <div><dt>User ID</dt><dd>{session.userId || "-"}</dd></div>
            <div><dt>角色</dt><dd>{session.role || "-"}</dd></div>
            <div><dt>账户 ID</dt><dd>{session.accountId || "-"}</dd></div>
            <div><dt>最近信号</dt><dd>{session.signalId || "-"}</dd></div>
            <div><dt>最近执行</dt><dd>{session.executionId || "-"}</dd></div>
          </dl>
        </section>

        <section className="panel login-panel">
          <div className="panel-heading">
            <h2>已有用户登录</h2>
            <span>可选</span>
          </div>
          <div className="form-row">
            <label>
              用户名或邮箱
              <input
                value={manualLogin.usernameOrEmail}
                onChange={(event) => setManualLogin({ ...manualLogin, usernameOrEmail: event.target.value })}
                placeholder="username@example.com"
              />
            </label>
            <label>
              密码
              <input
                type="password"
                value={manualLogin.password}
                onChange={(event) => setManualLogin({ ...manualLogin, password: event.target.value })}
                placeholder="password"
              />
            </label>
            <button onClick={loginExisting} disabled={busy || !manualLogin.usernameOrEmail || !manualLogin.password}>
              登录
            </button>
          </div>
        </section>


        {session.role === "super_admin" && (
          <section className="panel storage-panel">
            <div className="panel-heading">
              <div>
                <h2>存储位置</h2>
                <p className="panel-note">服务器预注册白名单，只读显示</p>
              </div>
              <button onClick={refreshStorageLocations} disabled={busy}>
                刷新
              </button>
            </div>
            <div className="storage-list">
              {storageLocations.length === 0 ? (
                <div className="empty-log">未配置可用存储位置</div>
              ) : (
                storageLocations.map((location) => (
                  <div className="storage-row" key={location.id}>
                    <div>
                      <strong>{location.label}</strong>
                      <span>{location.path}</span>
                    </div>
                    <span className={location.is_current ? "current-storage" : "standby-storage"}>
                      {location.is_current ? "当前配置" : "可选"}
                    </span>
                  </div>
                ))
              )}
            </div>
          </section>
        )}

        <section className="panel log-panel">
          <div className="panel-heading">
            <h2>执行日志</h2>
            <span>{logs.length} 条</span>
          </div>
          <div className="logs">
            {logs.length === 0 ? (
              <div className="empty-log">等待操作</div>
            ) : (
              logs.map((entry, index) => (
                <article className={entry.ok ? "log-entry ok" : "log-entry error"} key={`${entry.label}-${index}`}>
                  <header>
                    <strong>{entry.label}</strong>
                    <span>{entry.ok ? "PASS" : "FAIL"}</span>
                  </header>
                  <pre>{entry.detail}</pre>
                </article>
              ))
            )}
          </div>
        </section>
      </div>
    </main>
  );
}