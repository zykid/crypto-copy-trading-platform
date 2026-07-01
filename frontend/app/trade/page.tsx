"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type SessionState = {
  token: string;
  userId: string;
  username: string;
  role: string;
};

type ExchangeName = "binance" | "bybit" | "okx" | "mock";
type AccountMode = "SIMULATION" | "TESTNET" | "REAL";

type ExchangeAccount = {
  id: string;
  user_id?: string;
  exchange_name: ExchangeName;
  account_label: string;
  account_mode: AccountMode;
  trading_enabled: boolean;
  is_active: boolean;
};

type ApiKeyMetadata = {
  exchange_account_id: string;
  configured: boolean;
  has_passphrase: boolean;
  warning?: string;
};

type OrderSide = "BUY" | "SELL";

type ApiActionLog = {
  id: string;
  title: string;
  ok: boolean;
  detail: unknown;
};

type AuditLogRecord = {
  id: string;
  user_id: string;
  exchange_account_id: string | null;
  action: string;
  severity: string;
  payload: Record<string, unknown>;
  created_at: string | null;
};

type BottomTab = "positions" | "orders" | "history" | "audit";

const emptySession: SessionState = {
  token: "",
  userId: "",
  username: "",
  role: "",
};

const emptyMetadata: ApiKeyMetadata = {
  exchange_account_id: "",
  configured: false,
  has_passphrase: false,
};

const apiBaseFallback = "http://192.168.2.42:8000/api/v1";
const exchanges: ExchangeName[] = ["okx", "binance", "bybit", "mock"];
const symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"];
const sensitiveKeys = new Set([
  "api_key",
  "apiKey",
  "api_secret",
  "apiSecret",
  "password",
  "passphrase",
  "secret",
  "token",
  "reauthentication_token",
]);

function resolveApiBase() {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (configured) {
    return configured.replace(/\/$/, "");
  }
  return apiBaseFallback;
}

function readStoredToken() {
  if (typeof window === "undefined") {
    return "";
  }
  return localStorage.getItem("trading_platform_token") ?? "";
}

function sanitizeDetail(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeDetail(item));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, detail]) => [
        key,
        sensitiveKeys.has(key) ? "[redacted]" : sanitizeDetail(detail),
      ]),
    );
  }
  return value;
}

function prettyJson(value: unknown) {
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(sanitizeDetail(value), null, 2);
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function defaultAccountLabel(exchangeName: ExchangeName, mode: AccountMode) {
  if (exchangeName === "mock") {
    return "Mock Simulation";
  }
  if (mode === "REAL") {
    return `${exchangeName.toUpperCase()} Production Read Only`;
  }
  return `${exchangeName.toUpperCase()} Testnet Read Only`;
}

export default function TradeWorkspace() {
  const [apiRoot] = useState(resolveApiBase);
  const [session, setSession] = useState<SessionState>(emptySession);
  const [accounts, setAccounts] = useState<ExchangeAccount[]>([]);
  const [activeExchange, setActiveExchange] = useState<ExchangeName>("okx");
  const [activeSymbol, setActiveSymbol] = useState("BTC/USDT");
  const [activeAccountId, setActiveAccountId] = useState("");
  const [orderSide, setOrderSide] = useState<OrderSide>("BUY");
  const [lastStatus, setLastStatus] = useState("READ ONLY");
  const [apiKeyMetadata, setApiKeyMetadata] = useState<ApiKeyMetadata>(emptyMetadata);
  const [apiBusy, setApiBusy] = useState(false);
  const [apiLogs, setApiLogs] = useState<ApiActionLog[]>([]);
  const [bottomTab, setBottomTab] = useState<BottomTab>("positions");
  const [auditBusy, setAuditBusy] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [auditLoadedAt, setAuditLoadedAt] = useState("");
  const [selectedAuditLogId, setSelectedAuditLogId] = useState("");
  const [auditFilters, setAuditFilters] = useState({
    userId: "",
    exchangeAccountId: "",
    action: "",
    severity: "",
    limit: "50",
  });
  const [createForm, setCreateForm] = useState({
    exchangeName: "okx" as ExchangeName,
    accountMode: "TESTNET" as AccountMode,
    accountLabel: "",
  });
  const [secretForm, setSecretForm] = useState({
    apiKey: "",
    apiSecret: "",
    passphrase: "",
    password: "",
  });

  const appendApiLog = useCallback((title: string, ok: boolean, detail: unknown) => {
    setApiLogs((current) => [
      { id: crypto.randomUUID(), title, ok, detail: sanitizeDetail(detail) },
      ...current.slice(0, 5),
    ]);
    setLastStatus(ok ? "PASS" : "FAIL");
  }, []);

  const apiRequest = useCallback(
    async (
      method: "GET" | "POST" | "PATCH" | "DELETE",
      path: string,
      body?: unknown,
      expectedStatus = 200,
      extraHeaders: Record<string, string> = {},
    ) => {
      const token = readStoredToken();
      const response = await fetch(`${apiRoot}${path}`, {
        method,
        headers: {
          ...(body ? { "Content-Type": "application/json" } : {}),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...extraHeaders,
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      const payload = response.status === 204 ? null : await response.json().catch(() => null);
      if (response.status !== expectedStatus) {
        throw new Error(`${method} ${path} returned ${response.status}: ${prettyJson(payload)}`);
      }
      return payload;
    },
    [apiRoot],
  );

  const refreshAccounts = useCallback(async () => {
    const payload = await apiRequest("GET", "/exchange-accounts");
    setAccounts(Array.isArray(payload) ? (payload as ExchangeAccount[]) : []);
  }, [apiRequest]);

  useEffect(() => {
    const token = readStoredToken();
    if (!token) {
      return;
    }

    async function loadSession() {
      const headers = { Authorization: `Bearer ${token}` };
      const [meResponse, accountsResponse] = await Promise.all([
        fetch(`${apiRoot}/users/me`, { headers }),
        fetch(`${apiRoot}/exchange-accounts`, { headers }),
      ]);

      if (!meResponse.ok) {
        localStorage.removeItem("trading_platform_token");
        setSession(emptySession);
        return;
      }

      const me = (await meResponse.json()) as Record<string, string>;
      const accountPayload = accountsResponse.ok
        ? ((await accountsResponse.json()) as ExchangeAccount[])
        : [];

      setSession({
        token,
        userId: me.id ?? "",
        username: me.username ?? me.email ?? "",
        role: me.role ?? "",
      });
      setAccounts(accountPayload);
    }

    void loadSession().catch(() => setLastStatus("SESSION CHECK FAILED"));
  }, [apiRoot]);

  const exchangeAccounts = useMemo(
    () => accounts.filter((account) => account.exchange_name === activeExchange),
    [accounts, activeExchange],
  );
  const allSelectedAccount = accounts.find((account) => account.id === activeAccountId);

  useEffect(() => {
    if (exchangeAccounts.length === 0) {
      setActiveAccountId("");
      return;
    }
    if (!exchangeAccounts.some((account) => account.id === activeAccountId)) {
      setActiveAccountId(exchangeAccounts[0].id);
    }
  }, [activeAccountId, exchangeAccounts]);

  useEffect(() => {
    if (!activeAccountId || !session.token) {
      setApiKeyMetadata(emptyMetadata);
      return;
    }
    let cancelled = false;
    async function loadMetadata() {
      try {
        const metadata = (await apiRequest(
          "GET",
          `/exchange-accounts/${activeAccountId}/api-key`,
        )) as ApiKeyMetadata;
        if (!cancelled) {
          setApiKeyMetadata(metadata);
        }
      } catch (error) {
        if (!cancelled) {
          setApiKeyMetadata(emptyMetadata);
          appendApiLog("Read API key metadata", false, String(error));
        }
      }
    }
    void loadMetadata();
    return () => {
      cancelled = true;
    };
  }, [activeAccountId, apiRequest, appendApiLog, session.token]);

  const activeAccount = allSelectedAccount;
  const accountMode = activeAccount?.account_mode ?? "UNSELECTED";
  const canViewAuditLogs = session.role === "super_admin" || session.role === "admin";
  const selectedAuditLog = auditLogs.find((record) => record.id === selectedAuditLogId);
  const auditSeverityCounts = auditLogs.reduce<Record<string, number>>((counts, record) => {
    counts[record.severity] = (counts[record.severity] ?? 0) + 1;
    return counts;
  }, {});
  const orderLocked =
    !session.token ||
    accountMode === "REAL" ||
    !activeAccount?.trading_enabled ||
    activeExchange !== "mock";

  const marketRows = [
    { price: "68,420.5", amount: "0.184", side: "ask" },
    { price: "68,418.2", amount: "0.076", side: "ask" },
    { price: "68,410.0", amount: "0.214", side: "bid" },
    { price: "68,405.4", amount: "0.092", side: "bid" },
  ];

  async function createAccount() {
    if (!session.token) {
      appendApiLog("Create account", false, "Please log in first");
      return;
    }
    setApiBusy(true);
    try {
      const account = (await apiRequest(
        "POST",
        "/exchange-accounts",
        {
          exchange_name: createForm.exchangeName,
          account_label:
            createForm.accountLabel.trim() ||
            defaultAccountLabel(createForm.exchangeName, createForm.accountMode),
          account_mode: createForm.accountMode,
          trading_enabled: createForm.exchangeName === "mock",
        },
        201,
      )) as ExchangeAccount;
      await refreshAccounts();
      setActiveExchange(account.exchange_name);
      setActiveAccountId(account.id);
      appendApiLog("Create exchange account", true, account);
    } catch (error) {
      appendApiLog("Create exchange account", false, String(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function createReauthenticationToken(password: string) {
    const payload = (await apiRequest("POST", "/auth/reauthenticate", { password })) as {
      reauthentication_token?: string;
    };
    if (!payload.reauthentication_token) {
      throw new Error("reauthentication token missing");
    }
    return payload.reauthentication_token;
  }

  async function saveApiKey() {
    if (!activeAccount) {
      appendApiLog("Save encrypted API key", false, "Please select an account first");
      return;
    }
    if (activeAccount.exchange_name === "okx" && !secretForm.passphrase) {
      appendApiLog("Save encrypted API key", false, "OKX requires API passphrase");
      return;
    }
    setApiBusy(true);
    try {
      const reauthToken = await createReauthenticationToken(secretForm.password);
      const metadata = (await apiRequest(
        "POST",
        `/exchange-accounts/${activeAccount.id}/api-key`,
        {
          api_key: secretForm.apiKey,
          api_secret: secretForm.apiSecret,
          passphrase: secretForm.passphrase || null,
        },
        200,
        { "X-Reauthentication-Token": reauthToken },
      )) as ApiKeyMetadata;
      setApiKeyMetadata(metadata);
      setSecretForm({
        apiKey: "",
        apiSecret: "",
        passphrase: "",
        password: "",
      });
      appendApiLog("Save encrypted API key", true, metadata);
    } catch (error) {
      appendApiLog("Save encrypted API key", false, String(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function runReadOnlyCheck() {
    if (!activeAccount) {
      appendApiLog("Run read-only authentication", false, "Please select an account first");
      return;
    }
    if (activeAccount.account_mode === "SIMULATION") {
      appendApiLog("Run read-only authentication", false, "SIMULATION accounts do not use exchange API");
      return;
    }
    setApiBusy(true);
    try {
      const reauthToken = await createReauthenticationToken(secretForm.password);
      const checkPath =
        activeAccount.account_mode === "REAL"
          ? "real-read-only-check"
          : "testnet-read-only-check";
      const result = await apiRequest(
        "POST",
        `/exchange-accounts/${activeAccount.id}/${checkPath}`,
        undefined,
        200,
        { "X-Reauthentication-Token": reauthToken },
      );
      appendApiLog("Run read-only authentication", true, result);
    } catch (error) {
      appendApiLog("Run read-only authentication", false, String(error));
    } finally {
      setApiBusy(false);
    }
  }

  function setAuditFilterPreset(preset: "currentUser" | "currentAccount" | "errors" | "clear") {
    setAuditFilters((current) => {
      if (preset === "currentUser") {
        return { ...current, userId: session.userId };
      }
      if (preset === "currentAccount") {
        return { ...current, exchangeAccountId: activeAccountId };
      }
      if (preset === "errors") {
        return { ...current, severity: "ERROR" };
      }
      return {
        userId: "",
        exchangeAccountId: "",
        action: "",
        severity: "",
        limit: current.limit,
      };
    });
  }

  async function loadAuditLogs() {
    if (!canViewAuditLogs) {
      appendApiLog("Load audit logs", false, "Admin role required");
      return;
    }
    setAuditBusy(true);
    try {
      const params = new URLSearchParams();
      if (auditFilters.userId.trim()) {
        params.set("user_id", auditFilters.userId.trim());
      }
      if (auditFilters.exchangeAccountId.trim()) {
        params.set("exchange_account_id", auditFilters.exchangeAccountId.trim());
      }
      if (auditFilters.action.trim()) {
        params.set("action", auditFilters.action.trim());
      }
      if (auditFilters.severity.trim()) {
        params.set("severity", auditFilters.severity.trim());
      }
      params.set("limit", auditFilters.limit || "50");

      const payload = await apiRequest("GET", `/admin/observability/audit-logs?${params}`);
      if (!Array.isArray(payload)) {
        throw new Error("audit log response is not an array");
      }
      setAuditLogs(payload as AuditLogRecord[]);
      setSelectedAuditLogId(payload[0]?.id ?? "");
      setAuditLoadedAt(new Date().toLocaleString());
      appendApiLog("Load audit logs", true, {
        count: payload.length,
        action: auditFilters.action || "*",
        severity: auditFilters.severity || "*",
      });
    } catch (error) {
      appendApiLog("Load audit logs", false, String(error));
    } finally {
      setAuditBusy(false);
    }
  }

  return (
    <main className="trade-terminal">
      <aside className="trade-sidebar">
        <a className="trade-brand" href="/">
          <span>CT</span>
          <strong>Copy Trading</strong>
        </a>
        <nav>
          <a className="active" href="/trade">
            Trading
          </a>
          <a href="/">Console</a>
          <a href="/login">Login</a>
        </nav>
        <div className="trade-guardrail">
          <span>Guardrail</span>
          <strong>NO LIVE ORDER</strong>
          <p>REAL accounts are read-only in this stage. Mock is the only executable route.</p>
        </div>
      </aside>

      <section className="trade-main">
        <header className="trade-topbar">
          <div>
            <span className="trade-kicker">Exchange Workspace</span>
            <h1>{activeSymbol} Unified Trading</h1>
          </div>
          <div className="trade-user-pill">
            <span>{session.token ? session.username : "Not logged in"}</span>
            <strong>{session.role || "guest"}</strong>
          </div>
        </header>

        <section className="trade-market-strip">
          {exchanges.map((exchange) => (
            <button
              className={exchange === activeExchange ? "active" : ""}
              key={exchange}
              onClick={() => {
                setActiveExchange(exchange);
                setCreateForm((current) => ({
                  ...current,
                  exchangeName: exchange,
                  accountMode: exchange === "mock" ? "SIMULATION" : current.accountMode,
                }));
              }}
            >
              {exchange.toUpperCase()}
            </button>
          ))}
          {symbols.map((symbol) => (
            <button
              className={symbol === activeSymbol ? "symbol-active" : ""}
              key={symbol}
              onClick={() => setActiveSymbol(symbol)}
            >
              {symbol}
            </button>
          ))}
        </section>

        <section className="trade-layout-grid">
          <div className="trade-card trade-chart">
            <div className="trade-card-head">
              <div>
                <span>Chart</span>
                <strong>
                  {activeExchange.toUpperCase()} 路 {activeSymbol}
                </strong>
              </div>
              <em>{accountMode}</em>
            </div>
            <div className="trade-chart-canvas" aria-label="market chart preview">
              {Array.from({ length: 34 }, (_, index) => (
                <span
                  className={index % 3 === 0 ? "down" : "up"}
                  key={index}
                  style={{ height: `${28 + ((index * 13) % 112)}px` }}
                />
              ))}
            </div>
          </div>

          <div className="trade-card trade-orderbook">
            <div className="trade-card-head">
              <strong>Order Book</strong>
              <span>Read only</span>
            </div>
            {marketRows.map((row) => (
              <div className={`book-row ${row.side}`} key={`${row.price}-${row.amount}`}>
                <span>{row.price}</span>
                <span>{row.amount}</span>
              </div>
            ))}
          </div>

          <div className="trade-card trade-ticket">
            <div className="trade-card-head">
              <strong>Order Ticket</strong>
              <span>{lastStatus}</span>
            </div>
            <div className="trade-side-switch" aria-label="order side selector">
              <button
                className={orderSide === "BUY" ? "buy active" : "buy"}
                onClick={() => setOrderSide("BUY")}
              >
                Buy
              </button>
              <button
                className={orderSide === "SELL" ? "sell active" : "sell"}
                onClick={() => setOrderSide("SELL")}
              >
                Sell
              </button>
            </div>
            <label>
              Price
              <input readOnly value="Market / Mock preview" />
            </label>
            <label>
              Quantity
              <input readOnly value="0.001" />
            </label>
            <label>
              Account
              <input readOnly value={activeAccount?.account_label ?? "No account selected"} />
            </label>
            <button className="trade-submit" disabled={orderLocked}>
              {orderLocked ? "Order Locked" : `${orderSide} Mock Preview`}
            </button>
            <p>
              Locked until explicit risk, MFA, approval window, and exchange mode checks pass.
            </p>
          </div>
        </section>

        <section className="trade-api-manager" id="api-management">
          <div className="trade-card-head">
            <div>
              <span>API Management</span>
              <strong>账户选择 / 密钥状态 / 只读认证</strong>
            </div>
            <button className="trade-secondary-button" onClick={refreshAccounts} disabled={!session.token || apiBusy}>
              Refresh
            </button>
          </div>

          <div className="trade-api-manager-grid">
            <div className="trade-api-panel">
              <h2>Account Selector</h2>
              <div className="trade-account-list">
                {exchangeAccounts.length === 0 ? (
                  <p className="trade-muted">当前交易所还没有账户。</p>
                ) : (
                  exchangeAccounts.map((account) => (
                    <button
                      className={
                        account.id === activeAccountId
                          ? "trade-account-option selected"
                          : "trade-account-option"
                      }
                      key={account.id}
                      onClick={() => setActiveAccountId(account.id)}
                    >
                      <strong>{account.account_label}</strong>
                      <span>
                        {account.account_mode} / {account.trading_enabled ? "TRADING ON" : "READ ONLY"}
                      </span>
                    </button>
                  ))
                )}
              </div>
              <dl className="trade-account-meta">
                <div>
                  <dt>Selected</dt>
                  <dd>{activeAccount?.account_label ?? "-"}</dd>
                </div>
                <div>
                  <dt>Secret</dt>
                  <dd>{apiKeyMetadata.configured ? "Configured" : "Not set"}</dd>
                </div>
                <div>
                  <dt>Passphrase</dt>
                  <dd>{apiKeyMetadata.has_passphrase ? "Yes" : "No"}</dd>
                </div>
              </dl>
            </div>

            <div className="trade-api-panel">
              <h2>Create Account</h2>
              <div className="trade-form-grid">
                <label>
                  Exchange
                  <select
                    value={createForm.exchangeName}
                    onChange={(event) => {
                      const exchangeName = event.target.value as ExchangeName;
                      setCreateForm((current) => ({
                        ...current,
                        exchangeName,
                        accountMode: exchangeName === "mock" ? "SIMULATION" : current.accountMode,
                      }));
                    }}
                  >
                    {exchanges.map((exchange) => (
                      <option key={exchange} value={exchange}>
                        {exchange.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Mode
                  <select
                    value={createForm.accountMode}
                    onChange={(event) =>
                      setCreateForm({
                        ...createForm,
                        accountMode: event.target.value as AccountMode,
                      })
                    }
                    disabled={createForm.exchangeName === "mock"}
                  >
                    <option value="SIMULATION">SIMULATION</option>
                    <option value="TESTNET">TESTNET</option>
                    <option value="REAL">REAL READ ONLY</option>
                  </select>
                </label>
                <label>
                  Label
                  <input
                    value={createForm.accountLabel}
                    onChange={(event) =>
                      setCreateForm({ ...createForm, accountLabel: event.target.value })
                    }
                    placeholder={defaultAccountLabel(createForm.exchangeName, createForm.accountMode)}
                  />
                </label>
              </div>
              <button
                className="trade-submit compact"
                onClick={createAccount}
                disabled={!session.token || apiBusy}
              >
                Create Account
              </button>
            </div>

            <div className="trade-api-panel">
              <h2>Encrypted Credentials</h2>
              <div className="trade-form-grid">
                <label>
                  API Key
                  <input
                    autoComplete="off"
                    type="password"
                    value={secretForm.apiKey}
                    onChange={(event) =>
                      setSecretForm({ ...secretForm, apiKey: event.target.value })
                    }
                  />
                </label>
                <label>
                  API Secret
                  <input
                    autoComplete="off"
                    type="password"
                    value={secretForm.apiSecret}
                    onChange={(event) =>
                      setSecretForm({ ...secretForm, apiSecret: event.target.value })
                    }
                  />
                </label>
                <label>
                  Passphrase
                  <input
                    autoComplete="off"
                    type="password"
                    value={secretForm.passphrase}
                    onChange={(event) =>
                      setSecretForm({ ...secretForm, passphrase: event.target.value })
                    }
                  />
                </label>
                <label className="span-2">
                  Current Password
                  <input
                    autoComplete="current-password"
                    type="password"
                    value={secretForm.password}
                    onChange={(event) =>
                      setSecretForm({ ...secretForm, password: event.target.value })
                    }
                  />
                </label>
              </div>
              <div className="trade-action-row">
                <button
                  className="trade-secondary-button"
                  onClick={saveApiKey}
                  disabled={
                    !activeAccount ||
                    !secretForm.apiKey ||
                    !secretForm.apiSecret ||
                    !secretForm.password ||
                    apiBusy
                  }
                >
                  Save Encrypted Key
                </button>
                <button
                  className="trade-submit compact"
                  onClick={runReadOnlyCheck}
                  disabled={!activeAccount || !secretForm.password || apiBusy}
                >
                  Run Read-only Check
                </button>
              </div>
            </div>
          </div>

          <div className="trade-action-log" aria-label="api management action log">
            {apiLogs.length === 0 ? (
              <p className="trade-muted">No API management action yet.</p>
            ) : (
              apiLogs.map((log) => (
                <article key={log.id}>
                  <div>
                    <strong>{log.title}</strong>
                    <span className={log.ok ? "log-ok" : "log-fail"}>{log.ok ? "PASS" : "FAIL"}</span>
                  </div>
                  <pre>{prettyJson(log.detail)}</pre>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="trade-api-grid">
          {exchanges.map((exchange) => {
            const count = accounts.filter((account) => account.exchange_name === exchange).length;
            return (
              <article className="trade-card" key={exchange}>
                <span>{exchange.toUpperCase()}</span>
                <strong>{count}</strong>
                <p>{count === 0 ? "No API account" : "Read-only/test account available"}</p>
              </article>
            );
          })}
        </section>

        <section className="trade-bottom-grid">
          <div className="trade-card">
            <div className="trade-tabs">
              <button
                className={bottomTab === "positions" ? "active" : ""}
                onClick={() => setBottomTab("positions")}
              >
                Positions
              </button>
              <button
                className={bottomTab === "orders" ? "active" : ""}
                onClick={() => setBottomTab("orders")}
              >
                Open Orders
              </button>
              <button
                className={bottomTab === "history" ? "active" : ""}
                onClick={() => setBottomTab("history")}
              >
                History
              </button>
              <button
                className={bottomTab === "audit" ? "active" : ""}
                onClick={() => setBottomTab("audit")}
              >
                Audit
              </button>
            </div>
            {bottomTab === "positions" && (
              <div className="trade-empty-table">
                No live position data loaded. Use Console for Mock chain validation.
              </div>
            )}
            {bottomTab === "orders" && (
              <div className="trade-empty-table">
                No exchange open orders loaded. REAL and TESTNET order submission stays locked in this view.
              </div>
            )}
            {bottomTab === "history" && (
              <div className="trade-empty-table">
                Execution history will show accepted Mock orders and read-only exchange probes.
              </div>
            )}
            {bottomTab === "audit" && (
              <div className="trade-audit-panel">
                <div className="trade-audit-heading">
                  <div>
                    <strong>Audit Log</strong>
                    <span>Append-only records, admin read-only query</span>
                  </div>
                  <span>{auditLogs.length} loaded{auditLoadedAt ? ` · ${auditLoadedAt}` : ""}</span>
                </div>
                {canViewAuditLogs ? (
                  <>
                    <div className="trade-audit-presets">
                      <button
                        className="trade-secondary-button"
                        onClick={() => setAuditFilterPreset("currentUser")}
                        disabled={!session.userId}
                      >
                        Current User
                      </button>
                      <button
                        className="trade-secondary-button"
                        onClick={() => setAuditFilterPreset("currentAccount")}
                        disabled={!activeAccountId}
                      >
                        Current Account
                      </button>
                      <button
                        className="trade-secondary-button"
                        onClick={() => setAuditFilterPreset("errors")}
                      >
                        Errors Only
                      </button>
                      <button
                        className="trade-secondary-button"
                        onClick={() => setAuditFilterPreset("clear")}
                      >
                        Clear Filters
                      </button>
                    </div>
                    <div className="trade-audit-filters">
                      <label>
                        User ID
                        <input
                          value={auditFilters.userId}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              userId: event.target.value,
                            }))
                          }
                          placeholder="optional"
                        />
                      </label>
                      <label>
                        Account ID
                        <input
                          value={auditFilters.exchangeAccountId}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              exchangeAccountId: event.target.value,
                            }))
                          }
                          placeholder="optional"
                        />
                      </label>
                      <label>
                        Action
                        <input
                          value={auditFilters.action}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              action: event.target.value,
                            }))
                          }
                          placeholder="exact action"
                        />
                      </label>
                      <label>
                        Severity
                        <select
                          value={auditFilters.severity}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              severity: event.target.value,
                            }))
                          }
                        >
                          <option value="">All</option>
                          <option value="INFO">INFO</option>
                          <option value="OK">OK</option>
                          <option value="WARNING">WARNING</option>
                          <option value="ERROR">ERROR</option>
                        </select>
                      </label>
                      <label>
                        Limit
                        <select
                          value={auditFilters.limit}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              limit: event.target.value,
                            }))
                          }
                        >
                          <option value="25">25</option>
                          <option value="50">50</option>
                          <option value="100">100</option>
                        </select>
                      </label>
                      <button
                        className="trade-secondary-button"
                        onClick={() => void loadAuditLogs()}
                        disabled={auditBusy || !session.token}
                      >
                        {auditBusy ? "Loading" : "Load"}
                      </button>
                    </div>
                    <div className="trade-audit-summary">
                      {["INFO", "OK", "WARNING", "ERROR"].map((severity) => (
                        <span key={severity}>
                          {severity} <strong>{auditSeverityCounts[severity] ?? 0}</strong>
                        </span>
                      ))}
                    </div>
                    {auditLogs.length === 0 ? (
                      <div className="trade-empty-table">
                        No audit records loaded. Use filters and Load to query.
                      </div>
                    ) : (
                      <div className="trade-audit-workspace">
                        <div className="trade-audit-table" role="table" aria-label="Audit log records">
                          <div className="trade-audit-table-head" role="row">
                            <span>Time</span>
                            <span>Severity</span>
                            <span>Action</span>
                            <span>User</span>
                            <span>Account</span>
                          </div>
                          {auditLogs.map((record) => (
                            <button
                              className={record.id === selectedAuditLogId ? "selected" : ""}
                              key={record.id}
                              onClick={() => setSelectedAuditLogId(record.id)}
                              role="row"
                            >
                              <span>{formatDateTime(record.created_at)}</span>
                              <em>{record.severity}</em>
                              <strong>{record.action}</strong>
                              <span>{record.user_id}</span>
                              <span>{record.exchange_account_id ?? "-"}</span>
                            </button>
                          ))}
                        </div>
                        <article className="trade-audit-detail">
                          {selectedAuditLog ? (
                            <>
                              <header>
                                <div>
                                  <span>Selected Record</span>
                                  <strong>{selectedAuditLog.action}</strong>
                                </div>
                                <em>{selectedAuditLog.severity}</em>
                              </header>
                              <dl>
                                <div>
                                  <dt>Created</dt>
                                  <dd>{formatDateTime(selectedAuditLog.created_at)}</dd>
                                </div>
                                <div>
                                  <dt>User</dt>
                                  <dd>{selectedAuditLog.user_id}</dd>
                                </div>
                                <div>
                                  <dt>Account</dt>
                                  <dd>{selectedAuditLog.exchange_account_id ?? "-"}</dd>
                                </div>
                                <div>
                                  <dt>ID</dt>
                                  <dd>{selectedAuditLog.id}</dd>
                                </div>
                              </dl>
                              <pre>{prettyJson(selectedAuditLog.payload)}</pre>
                            </>
                          ) : (
                            <div className="trade-empty-table">Select an audit record.</div>
                          )}
                        </article>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="trade-empty-table">
                    Admin-only audit view. Log in as admin or super_admin to query records.
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="trade-card">
            <div className="trade-card-head">
              <strong>Risk Snapshot</strong>
              <span>Unified</span>
            </div>
            <dl className="trade-risk-list">
              <div>
                <dt>Trading</dt>
                <dd>Disabled by default</dd>
              </div>
              <div>
                <dt>REAL</dt>
                <dd>Read only</dd>
              </div>
              <div>
                <dt>Latest result</dt>
                <dd>{lastStatus}</dd>
              </div>
            </dl>
          </div>
        </section>
      </section>
    </main>
  );
}
