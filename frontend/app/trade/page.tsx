"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import LiveMarketChart from "./LiveMarketChart";

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

type ExchangeAccountPayload = Partial<ExchangeAccount> & {
  account_id?: string;
  exchange?: ExchangeName;
  mode?: AccountMode;
  label?: string;
};

type ApiKeyMetadata = {
  exchange_account_id: string;
  configured: boolean;
  has_passphrase: boolean;
  warning?: string;
};

type MarketDataProvider = {
  id: string;
  name: string;
  base_url: string;
  configured: boolean;
  auth_required: boolean;
  read_only: boolean;
  supports: string[];
};

type Phase4ReadinessCheck = {
  name: string;
  status: string;
  required: boolean;
  detail: string;
};

type Phase4ReadinessReport = {
  exchange_account_id: string;
  exchange_name: ExchangeName;
  account_mode: AccountMode;
  overall_status: string;
  read_only: boolean;
  order_submission_authorized: boolean;
  checks: Phase4ReadinessCheck[];
  gate_reasons: string[];
};

type OrderSide = "BUY" | "SELL";
type OrderType = "MARKET" | "LIMIT";

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

type BottomTab = "balances" | "orders" | "history" | "audit";
type WorkspaceSection =
  | "terminal"
  | "portfolio"
  | "api-management"
  | "risk"
  | "audit"
  | "market-data"
  | "small-fund";
type AuditFilters = {
  userId: string;
  exchangeAccountId: string;
  action: string;
  severity: string;
  createdFrom: string;
  createdTo: string;
  limit: string;
};
type PreRealChecklistItem = {
  id: string;
  title: string;
  detail: string;
  required: boolean;
  status: "pass" | "pending" | "warn" | "fail";
};

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

type RealOpenOrder = {
  order_id: string | null;
  symbol: string | null;
  side: string | null;
  order_type: string | null;
  status: string | null;
  price: string | null;
  quantity: string | null;
  filled_quantity: string | null;
  created_at: string | null;
};
type RealBalance = {
  asset: string;
  free: string | null;
  locked: string | null;
  total: string | null;
};
const emptySecretForm = {
  apiKey: "",
  apiSecret: "",
  passphrase: "",
  password: "",
};

const apiBaseFallback = "http://localhost:8000/api/v1";
const exchanges: ExchangeName[] = ["okx", "binance", "bybit", "mock"];
const symbols = [
  "BTC/USDT",
  "ETH/USDT",
  "SOL/USDT",
  "BNB/USDT",
  "XRP/USDT",
  "DOGE/USDT",
  "ADA/USDT",
  "AVAX/USDT",
  "LINK/USDT",
  "TON/USDT",
  "BTC/USDC",
  "ETH/USDC",
];
const workspaceHashMap: Record<string, WorkspaceSection> = {
  "": "terminal",
  "#terminal": "terminal",
  "#portfolio": "portfolio",
  "#api-management": "api-management",
  "#risk": "risk",
  "#audit": "audit",
  "#market-data": "market-data",
  "#phase4-small-fund-review": "small-fund",
  "#pre-real-checklist": "small-fund",
  "#small-fund-final-readiness": "small-fund",
  "#phase4-real-order-window": "small-fund",
  "#phase4-final-release-check": "small-fund",
};
const workspaceLabels: Record<WorkspaceSection, string> = {
  terminal: "交易终端",
  portfolio: "资产概览",
  "api-management": "API 与账户",
  risk: "风控中心",
  audit: "审计中心",
  "market-data": "市场数据",
  "small-fund": "小额测试闸门",
};
const orderSideLabels: Record<OrderSide, string> = {
  BUY: "买入",
  SELL: "卖出",
};
const orderTypeLabels: Record<OrderType, string> = {
  MARKET: "市价",
  LIMIT: "限价",
};
const accountModeLabels: Record<AccountMode, string> = {
  SIMULATION: "模拟",
  TESTNET: "测试网",
  REAL: "真实只读",
};

const exchangeNames: readonly ExchangeName[] = ["binance", "bybit", "okx", "mock"];
const accountModes: readonly AccountMode[] = ["SIMULATION", "TESTNET", "REAL"];
const resultLabels: Record<string, string> = {
  PASS: "通过",
  FAIL: "失败",
  BLOCKED: "已锁定",
  PENDING: "待处理",
  WARN: "警告",
  READY_FOR_REVIEW: "可人工复核",
  READINESS_PASS: "准备就绪",
  READINESS_BLOCKED: "准备未完成",
  REVIEW_RECORDED: "复核已记录",
  NO_REVIEW_AUDIT: "无复核审计",
  READY_TO_RECORD: "可记录",
  WINDOW_LOCKED: "窗口已锁定",
  WINDOW_RECORDED: "窗口已记录",
  NO_WINDOW_AUDIT: "无窗口审计",
  FINAL_GATE_LOCKED: "终审已锁定",
  FINAL_CHECK_RECORDED: "终审已记录",
  NO_FINAL_CHECK: "无终审记录",
  COMPLETE: "完成",
  INCOMPLETE: "未完成",
  LOCKED: "已锁定",
  MISSING: "缺失",
  RECORDED: "已记录",
  ON: "开启",
  OFF: "关闭",
  AUDIT_ONLY: "仅审计",
};
const severityLabels: Record<string, string> = {
  INFO: "信息",
  OK: "正常",
  WARNING: "警告",
  ERROR: "错误",
};
const auditActionOptions = [
  "real.read_only.authentication.checked",
  "real.small_fund.review_recorded",
  "real.small_fund.order_window.approval_recorded",
  "real.small_fund.final_release_check_recorded",
  "testnet.read_only.authentication.checked",
  "testnet.order_window.approval_recorded",
  "position_reconciliation.drift_detected",
  "position_reconciliation.matched",
  "user.reauthentication.succeeded",
  "user.reauthentication.failed",
  "user.password.changed",
  "user.mfa.enabled",
  "user.mfa.disabled",
  "super_admin.bootstrap.created",
];
const exchangeProfiles: Record<
  ExchangeName,
  {
    label: string;
    venue: string;
    route: string;
    window: string;
  }
> = {
  okx: {
    label: "OKX",
    venue: "统一账户",
    route: "真实 / 测试网只读",
    window: "余额、持仓和订单校验均保持只读。",
  },
  binance: {
    label: "Binance",
    venue: "现货 / 合约",
    route: "测试网只读",
    window: "适配器窗口保留用于测试网验证。",
  },
  bybit: {
    label: "Bybit",
    venue: "统一交易账户",
    route: "测试网只读",
    window: "适配器窗口保留用于测试网验证。",
  },
  mock: {
    label: "Mock 模拟交易所",
    venue: "模拟环境",
    route: "模拟可执行",
    window: "Mock 路由仅在账户交易标记与风控检查通过后执行。",
  },
};
const marketSnapshots: Record<string, { last: number; bid: number; ask: number; change: string }> = {
  "BTC/USDT": { last: 68420.5, bid: 68410, ask: 68428.2, change: "+1.42%" },
  "ETH/USDT": { last: 3582.16, bid: 3581.4, ask: 3583.2, change: "+0.86%" },
  "SOL/USDT": { last: 151.72, bid: 151.61, ask: 151.84, change: "-0.31%" },
  "BNB/USDT": { last: 612.3, bid: 612.1, ask: 612.6, change: "+0.24%" },
  "XRP/USDT": { last: 0.62, bid: 0.619, ask: 0.621, change: "-0.18%" },
  "DOGE/USDT": { last: 0.125, bid: 0.1248, ask: 0.1252, change: "+0.51%" },
  "ADA/USDT": { last: 0.41, bid: 0.409, ask: 0.411, change: "+0.12%" },
  "AVAX/USDT": { last: 27.84, bid: 27.8, ask: 27.88, change: "-0.44%" },
  "LINK/USDT": { last: 14.62, bid: 14.6, ask: 14.65, change: "+0.33%" },
  "TON/USDT": { last: 3.18, bid: 3.17, ask: 3.19, change: "+0.09%" },
  "BTC/USDC": { last: 68405.2, bid: 68398.4, ask: 68412.8, change: "+1.39%" },
  "ETH/USDC": { last: 3580.4, bid: 3579.6, ask: 3581.2, change: "+0.81%" },
};
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
const testnetOrderWindowApprovalAck = "APPROVE_TESTNET_ORDER_WINDOW_ONLY";
const phase4SmallFundReviewAck = "ACKNOWLEDGE_SMALL_FUND_REVIEW_ONLY";
const phase4SmallFundOrderWindowAck = "APPROVE_REAL_SMALL_FUND_ORDER_WINDOW_ONLY";
const phase4FinalReleaseCheckAck = "RECORD_PHASE4_FINAL_RELEASE_CHECK_ONLY";

function normalizeApiRoot(value: string) {
  const trimmed = value.replace(/\/$/, "");
  return trimmed.endsWith("/api/v1") ? trimmed : `${trimmed}/api/v1`;
}

function resolveApiBase() {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (typeof window !== "undefined" && (!configured || configured === "http://localhost:8000")) {
    return `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
  }
  if (configured) {
    return normalizeApiRoot(configured);
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
  try {
    if (typeof value === "string") {
      return value;
    }
    return (
      JSON.stringify(
        sanitizeDetail(value),
        (_key, item) => (typeof item === "bigint" ? item.toString() : item),
        2,
      ) ?? ""
    );
  } catch (error) {
    return `无法显示详情：${String(error)}`;
  }
}

function createClientLogId() {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return `log-${Date.now()}-${Math.random().toString(16).slice(2)}`;
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

function toAuditQueryDateTime(value: string) {
  if (!value.trim()) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    throw new Error(`审计日期筛选无效：${value}`);
  }
  return date.toISOString();
}

function defaultAccountLabel(exchangeName: ExchangeName, mode: AccountMode) {
  if (exchangeName === "mock") {
    return "Mock 模拟账户";
  }
  if (mode === "REAL") {
    return `${exchangeName.toUpperCase()} 正式只读账户`;
  }
  return `${exchangeName.toUpperCase()} 测试网只读账户`;
}

function safeAccountModeLabel(mode: AccountMode | string | undefined) {
  if (!mode) {
    return "未选择";
  }
  return accountModeLabels[mode as AccountMode] ?? String(mode);
}

function isExchangeName(value: unknown): value is ExchangeName {
  return typeof value === "string" && exchangeNames.includes(value as ExchangeName);
}

function isAccountMode(value: unknown): value is AccountMode {
  return typeof value === "string" && accountModes.includes(value as AccountMode);
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}

function normalizeExchangeAccount(value: unknown): ExchangeAccount | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const payload = value as ExchangeAccountPayload;
  const id = payload.id ?? payload.account_id;
  const exchangeName = payload.exchange_name ?? payload.exchange;
  const accountMode = payload.account_mode ?? payload.mode;
  if (typeof id !== "string" || !isExchangeName(exchangeName) || !isAccountMode(accountMode)) {
    return null;
  }
  return {
    id,
    user_id: payload.user_id,
    exchange_name: exchangeName,
    account_label: payload.account_label ?? payload.label ?? defaultAccountLabel(exchangeName, accountMode),
    account_mode: accountMode,
    trading_enabled: Boolean(payload.trading_enabled),
    is_active: payload.is_active ?? true,
  };
}

function normalizeExchangeAccounts(value: unknown): ExchangeAccount[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => normalizeExchangeAccount(item))
    .filter((account): account is ExchangeAccount => Boolean(account));
}

function formatNumber(value: number, maximumFractionDigits = 2) {
  if (!Number.isFinite(value)) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(value);
}

export default function TradeWorkspace() {
  const [apiRoot] = useState(resolveApiBase);
  const [session, setSession] = useState<SessionState>(emptySession);
  const [sessionChecked, setSessionChecked] = useState(false);
  const [accounts, setAccounts] = useState<ExchangeAccount[]>([]);
  const [activeExchange, setActiveExchange] = useState<ExchangeName>("okx");
  const [activeSymbol, setActiveSymbol] = useState("BTC/USDT");
  const [liveMarketPrice, setLiveMarketPrice] = useState<number | null>(null);
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceSection>("terminal");
  const [symbolSearch, setSymbolSearch] = useState("");
  const [favoriteSymbols, setFavoriteSymbols] = useState<string[]>(["BTC/USDT", "ETH/USDT", "SOL/USDT"]);
  const [activeAccountId, setActiveAccountId] = useState("");
  const [orderSide, setOrderSide] = useState<OrderSide>("BUY");
  const [orderForm, setOrderForm] = useState({
    orderType: "MARKET" as OrderType,
    price: "",
    quantity: "0.001",
  });
  const [lastStatus, setLastStatus] = useState("只读");
  const [apiKeyMetadata, setApiKeyMetadata] = useState<ApiKeyMetadata>(emptyMetadata);
  const [apiMetadataLoading, setApiMetadataLoading] = useState(false);
  const [apiBusy, setApiBusy] = useState(false);
  const [apiLogs, setApiLogs] = useState<ApiActionLog[]>([]);
  const [openOrders, setOpenOrders] = useState<RealOpenOrder[]>([]);
  const [openOrdersLoading, setOpenOrdersLoading] = useState(false);
  const [openOrdersLoadedAt, setOpenOrdersLoadedAt] = useState("");
  const [balances, setBalances] = useState<RealBalance[]>([]);
  const [balancesLoading, setBalancesLoading] = useState(false);
  const [balancesLoadedAt, setBalancesLoadedAt] = useState("");
  const [isOrderPreviewOpen, setIsOrderPreviewOpen] = useState(false);
  const [orderApprovalPassword, setOrderApprovalPassword] = useState("");
  const [phase4Readiness, setPhase4Readiness] = useState<Phase4ReadinessReport | null>(null);
  const [phase4MaxNotional, setPhase4MaxNotional] = useState("25");
  const [phase4ReviewPassword, setPhase4ReviewPassword] = useState("");
  const [phase4OrderWindowPassword, setPhase4OrderWindowPassword] = useState("");
  const [phase4OrderWindowDuration, setPhase4OrderWindowDuration] = useState("5");
  const [phase4FinalPassword, setPhase4FinalPassword] = useState("");
  const [phase4FinalConfirmations, setPhase4FinalConfirmations] = useState({
    dedicatedAccount: false,
    accountEmpty: false,
    withdrawalsDisabled: false,
    deleteApiKeyAfterTest: false,
    firstOrderStopReview: false,
    noLiveOrderSubmission: false,
  });
  const [bottomTab, setBottomTab] = useState<BottomTab>("balances");
  const [auditBusy, setAuditBusy] = useState(false);
  const [auditLogs, setAuditLogs] = useState<AuditLogRecord[]>([]);
  const [auditLoadedAt, setAuditLoadedAt] = useState("");
  const [selectedAuditLogId, setSelectedAuditLogId] = useState("");
  const [auditFilters, setAuditFilters] = useState<AuditFilters>({
    userId: "",
    exchangeAccountId: "",
    action: "",
    severity: "",
    createdFrom: "",
    createdTo: "",
    limit: "50",
  });
  const [createForm, setCreateForm] = useState({
    exchangeName: "okx" as ExchangeName,
    accountMode: "TESTNET" as AccountMode,
    accountLabel: "",
  });
  const [secretForm, setSecretForm] = useState(emptySecretForm);
  const [marketDataProviders, setMarketDataProviders] = useState<MarketDataProvider[]>([]);
  const [marketDataBusy, setMarketDataBusy] = useState(false);
  const [marketDataForm, setMarketDataForm] = useState({
    ticker: "SPX",
    package: "classic",
    category: "gex_full",
  });
  const [marketDataResult, setMarketDataResult] = useState<unknown>(null);

  const appendApiLog = useCallback((title: string, ok: boolean, detail: unknown) => {
    setApiLogs((current) => [
      { id: createClientLogId(), title, ok, detail: sanitizeDetail(detail) },
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

  const clearApiAccountState = useCallback(() => {
    setActiveAccountId("");
    setApiKeyMetadata(emptyMetadata);
    setApiMetadataLoading(false);
    setSecretForm(emptySecretForm);
    setOpenOrders([]);
    setOpenOrdersLoadedAt("");
    setBalances([]);
    setBalancesLoadedAt("");
  }, []);

  const refreshAccounts = useCallback(async (preferredAccountId = "") => {
    const payload = await apiRequest("GET", "/exchange-accounts");
    const nextAccounts = normalizeExchangeAccounts(payload);
    setAccounts(nextAccounts);
    const currentAccountId = activeAccountId;
    const nextActiveAccountId =
      preferredAccountId && nextAccounts.some((account) => account.id === preferredAccountId)
        ? preferredAccountId
        : currentAccountId && nextAccounts.some((account) => account.id === currentAccountId)
          ? currentAccountId
          : "";
    setActiveAccountId(nextActiveAccountId);
    if (!nextActiveAccountId) {
      setApiKeyMetadata(emptyMetadata);
      setApiMetadataLoading(false);
      setSecretForm(emptySecretForm);
    }
    return nextAccounts;
  }, [activeAccountId, apiRequest]);

  const refreshMarketDataProviders = useCallback(async () => {
    const payload = (await apiRequest("GET", "/market-data/providers")) as {
      providers?: MarketDataProvider[];
    };
    setMarketDataProviders(Array.isArray(payload.providers) ? payload.providers : []);
  }, [apiRequest]);

  useEffect(() => {
    const token = readStoredToken();
    if (!token) {
      setSessionChecked(true);
      window.location.replace("/login");
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
        setSessionChecked(true);
        window.location.replace("/login");
        return;
      }

      const me = (await meResponse.json()) as Record<string, string>;
      const accountPayload = accountsResponse.ok ? await accountsResponse.json() : [];

      setSession({
        token,
        userId: me.id ?? "",
        username: me.username ?? me.email ?? "",
        role: me.role ?? "",
      });
      setAccounts(normalizeExchangeAccounts(accountPayload));
      setSessionChecked(true);
    }

    void loadSession().catch(() => {
      localStorage.removeItem("trading_platform_token");
      setSession(emptySession);
      setLastStatus("会话检查失败");
      setSessionChecked(true);
      window.location.replace("/login");
    });
  }, [apiRoot]);

  useEffect(() => {
    if (!session.token) {
      setMarketDataProviders([]);
      return;
    }
    void refreshMarketDataProviders().catch((error) =>
      appendApiLog("加载市场数据服务商", false, errorMessage(error)),
    );
  }, [appendApiLog, refreshMarketDataProviders, session.token]);

  const exchangeAccounts = useMemo(
    () => accounts.filter((account) => account.exchange_name === activeExchange),
    [accounts, activeExchange],
  );
  const allSelectedAccount = accounts.find((account) => account.id === activeAccountId);
  const selectedMetadataAccountId = allSelectedAccount?.id ?? "";

  useEffect(() => {
    if (!activeAccountId) {
      return;
    }
    if (!accounts.some((account) => account.id === activeAccountId)) {
      clearApiAccountState();
    }
  }, [activeAccountId, accounts, clearApiAccountState]);

  useEffect(() => {
    if (!selectedMetadataAccountId || !session.token) {
      setApiKeyMetadata(emptyMetadata);
      setApiMetadataLoading(false);
      return;
    }
    let cancelled = false;
    async function loadMetadata() {
      setApiKeyMetadata(emptyMetadata);
      setApiMetadataLoading(true);
      try {
        const metadata = (await apiRequest(
          "GET",
          `/exchange-accounts/${selectedMetadataAccountId}/api-key`,
        )) as ApiKeyMetadata;
        if (!cancelled) {
          setApiKeyMetadata(metadata);
        }
      } catch (error) {
        if (!cancelled) {
          setApiKeyMetadata(emptyMetadata);
          appendApiLog("读取 API Key 状态", false, errorMessage(error));
        }
      } finally {
        if (!cancelled) {
          setApiMetadataLoading(false);
        }
      }
    }
    void loadMetadata();
    return () => {
      cancelled = true;
    };
  }, [selectedMetadataAccountId, apiRequest, appendApiLog, session.token]);

  useEffect(() => {
    setPhase4Readiness(null);
    setPhase4ReviewPassword("");
    setPhase4OrderWindowPassword("");
    setPhase4FinalPassword("");
  }, [activeAccountId]);

  useEffect(() => {
    function syncHashToPanel() {
      const workspace = workspaceHashMap[window.location.hash] ?? "terminal";
      setActiveWorkspace(workspace);
      if (workspace === "audit") {
        setBottomTab("audit");
      }
    }

    syncHashToPanel();
    window.addEventListener("hashchange", syncHashToPanel);
    return () => window.removeEventListener("hashchange", syncHashToPanel);
  }, []);

  useEffect(() => {
    const stored = window.localStorage.getItem("favorite_trading_symbols");
    if (!stored) {
      return;
    }
    try {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        const knownSymbols = parsed.filter((symbol): symbol is string => symbols.includes(symbol));
        if (knownSymbols.length > 0) {
          setFavoriteSymbols(knownSymbols);
        }
      }
    } catch {
      window.localStorage.removeItem("favorite_trading_symbols");
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem("favorite_trading_symbols", JSON.stringify(favoriteSymbols));
  }, [favoriteSymbols]);

  const activeAccount = allSelectedAccount;
  const selectedApiKeyMetadata =
    activeAccount && apiKeyMetadata.exchange_account_id === activeAccount.id
      ? apiKeyMetadata
      : emptyMetadata;
  const canLoadOpenOrders = Boolean(
    activeAccount &&
      activeAccount.exchange_name === "okx" &&
      activeAccount.account_mode === "REAL" &&
      activeAccount.is_active &&
      !activeAccount.trading_enabled &&
      selectedApiKeyMetadata.configured,
  );
  const canLoadBalances = canLoadOpenOrders;
  const accountMode = activeAccount?.account_mode ?? "UNSELECTED";
  const activeExchangeProfile = exchangeProfiles[activeExchange];
  const activeWorkspaceLabel = workspaceLabels[activeWorkspace];
  const activeAccountHealth = !activeAccount
    ? "未绑定账户"
    : activeAccount.is_active
      ? activeAccount.trading_enabled
        ? "交易已开启"
        : "只读"
      : "未启用";
  const selectedAccountRoute = activeAccount
    ? `${activeExchangeProfile.label} / ${safeAccountModeLabel(activeAccount.account_mode)} / ${
        activeAccount.trading_enabled ? "交易标记已开启" : "只读标记"
      }`
    : "请选择交易所账户绑定当前下单面板。";
  const activeExchangeAccounts = accounts.filter((account) => account.exchange_name === activeExchange);
  const accountModeSummary = {
    simulation: accounts.filter((account) => account.account_mode === "SIMULATION").length,
    testnet: accounts.filter((account) => account.account_mode === "TESTNET").length,
    real: accounts.filter((account) => account.account_mode === "REAL").length,
    tradingEnabled: accounts.filter((account) => account.trading_enabled).length,
  };
  const activeMarket = marketSnapshots[activeSymbol] ?? marketSnapshots["BTC/USDT"];
  const favoriteSymbolSet = useMemo(() => new Set(favoriteSymbols), [favoriteSymbols]);
  const filteredSymbols = useMemo(() => {
    const query = symbolSearch.trim().toUpperCase().replace("/", "");
    return symbols
      .filter((symbol) => !query || symbol.replace("/", "").includes(query) || symbol.includes(query))
      .sort((left, right) => {
        const favoriteDiff = Number(favoriteSymbolSet.has(right)) - Number(favoriteSymbolSet.has(left));
        return favoriteDiff || left.localeCompare(right);
      });
  }, [favoriteSymbolSet, symbolSearch]);
  const favoritePinnedSymbols = symbols.filter((symbol) => favoriteSymbolSet.has(symbol)).slice(0, 5);
  const toggleFavoriteSymbol = useCallback((symbol: string) => {
    setFavoriteSymbols((current) =>
      current.includes(symbol) ? current.filter((item) => item !== symbol) : [symbol, ...current],
    );
  }, []);
  const parsedPrice = Number(orderForm.price);
  const parsedQuantity = Number(orderForm.quantity);
  const referencePrice =
    orderForm.orderType === "LIMIT" && Number.isFinite(parsedPrice) && parsedPrice > 0
      ? parsedPrice
      : liveMarketPrice ?? activeMarket.last;
  const estimatedNotional =
    Number.isFinite(parsedQuantity) && parsedQuantity > 0 ? parsedQuantity * referencePrice : 0;
  const normalizedPreviewSymbol = activeSymbol.replace("/", "");
  const clientOrderIdPreview = activeAccount?.id
    ? `preview-${activeExchange}-${activeAccount.id.slice(0, 8)}-${activeSymbol.replace("/", "")}`
    : "preview-unassigned";
  const orderPreviewPayload = {
    route_status: "preview_only",
    exchange_name: activeExchange,
    exchange_label: activeExchangeProfile.label,
    exchange_account_id: activeAccount?.id ?? null,
    account_label: activeAccount?.account_label ?? null,
    account_mode: activeAccount?.account_mode ?? null,
    symbol: normalizedPreviewSymbol,
    display_symbol: activeSymbol,
    side: orderSide,
    order_type: orderForm.orderType,
    reference_price: referencePrice,
    quantity: Number.isFinite(parsedQuantity) ? parsedQuantity : null,
    estimated_notional: estimatedNotional,
    client_order_id: clientOrderIdPreview,
    secret_configured: selectedApiKeyMetadata.configured,
    trading_enabled: activeAccount?.trading_enabled ?? false,
  };
  const lockReasons = [
    !session.token ? "需要先登录" : null,
    !activeAccount ? "请选择交易所账户" : null,
    activeAccount && !activeAccount.is_active ? "账户未启用" : null,
    activeAccount?.account_mode === "REAL" ? "当前阶段真实账户保持只读" : null,
    activeExchange !== "mock" ? "当前下单面板仅允许 Mock 执行" : null,
    activeAccount && !activeAccount.trading_enabled ? "账户交易标记未开启" : null,
    !Number.isFinite(parsedQuantity) || parsedQuantity <= 0 ? "数量必须大于 0" : null,
    orderForm.orderType === "LIMIT" && (!Number.isFinite(parsedPrice) || parsedPrice <= 0)
      ? "限价单必须填写有效价格"
      : null,
  ].filter(Boolean) as string[];
  const testnetWindowReasons = [
    !session.token ? "需要先登录" : null,
    !activeAccount ? "请选择交易所账户" : null,
    activeAccount && !activeAccount.is_active ? "账户未启用" : null,
    activeAccount?.account_mode !== "TESTNET" ? "账户模式必须为测试网" : null,
    activeExchange === "mock" ? "Mock 使用模拟流程，不进入测试网窗口" : null,
    activeAccount?.trading_enabled ? "审批前账户交易标记必须保持关闭" : null,
    !selectedApiKeyMetadata.configured ? "需要先配置加密 API Key 元数据" : null,
    !Number.isFinite(parsedQuantity) || parsedQuantity <= 0 ? "数量必须大于 0" : null,
    estimatedNotional <= 0 ? "预估名义金额必须大于 0" : null,
  ].filter(Boolean) as string[];
  const canViewAuditLogs = session.role === "super_admin" || session.role === "admin";
  const selectedAuditLog = auditLogs.find((record) => record.id === selectedAuditLogId);
  const approvalAuditLogs = auditLogs.filter(
    (record) => record.action === "testnet.order_window.approval_recorded",
  );
  const phase4ReviewAuditLogs = auditLogs.filter(
    (record) => record.action === "real.small_fund.review_recorded",
  );
  const phase4OrderWindowAuditLogs = auditLogs.filter(
    (record) => record.action === "real.small_fund.order_window.approval_recorded",
  );
  const phase4FinalReleaseAuditLogs = auditLogs.filter(
    (record) => record.action === "real.small_fund.final_release_check_recorded",
  );
  const latestApprovalAuditLog = approvalAuditLogs[0] ?? null;
  const latestPhase4ReviewAuditLog = phase4ReviewAuditLogs[0] ?? null;
  const latestPhase4OrderWindowAuditLog = phase4OrderWindowAuditLogs[0] ?? null;
  const latestPhase4FinalReleaseAuditLog = phase4FinalReleaseAuditLogs[0] ?? null;
  const selectedApprovalPayload =
    selectedAuditLog?.action === "testnet.order_window.approval_recorded" ||
    selectedAuditLog?.action === "real.small_fund.order_window.approval_recorded" ||
    selectedAuditLog?.action === "real.small_fund.final_release_check_recorded"
      ? selectedAuditLog.payload
      : null;
  const phase4MaxNotionalValue = Number(phase4MaxNotional);
  const activePhase4Ready =
    phase4Readiness?.exchange_account_id === activeAccountId &&
    phase4Readiness.overall_status === "PASS" &&
    phase4Readiness.read_only &&
    !phase4Readiness.order_submission_authorized;
  const canRecordPhase4SmallFundReview =
    Boolean(activeAccount) &&
    activeAccount?.account_mode === "REAL" &&
    activeAccount?.exchange_name === "okx" &&
    session.role === "super_admin" &&
    activePhase4Ready &&
    Number.isFinite(phase4MaxNotionalValue) &&
    phase4MaxNotionalValue > 0 &&
    phase4MaxNotionalValue <= 100 &&
    Boolean(phase4ReviewPassword);
  const phase4OrderWindowDurationValue = Number(phase4OrderWindowDuration);
  const canRecordPhase4OrderWindow =
    Boolean(activeAccount) &&
    activeAccount?.account_mode === "REAL" &&
    activeAccount?.exchange_name === "okx" &&
    session.role === "super_admin" &&
    activePhase4Ready &&
    Boolean(latestPhase4ReviewAuditLog) &&
    orderForm.orderType === "LIMIT" &&
    Number.isFinite(parsedQuantity) &&
    parsedQuantity > 0 &&
    Number.isFinite(parsedPrice) &&
    parsedPrice > 0 &&
    estimatedNotional > 0 &&
    estimatedNotional <= phase4MaxNotionalValue &&
    Number.isFinite(phase4OrderWindowDurationValue) &&
    phase4OrderWindowDurationValue >= 1 &&
    phase4OrderWindowDurationValue <= 10 &&
    Boolean(phase4OrderWindowPassword);
  const allPhase4FinalConfirmations = Object.values(phase4FinalConfirmations).every(Boolean);
  const canRecordPhase4FinalReleaseCheck =
    Boolean(activeAccount) &&
    activeAccount?.account_mode === "REAL" &&
    activeAccount?.exchange_name === "okx" &&
    session.role === "super_admin" &&
    activePhase4Ready &&
    Boolean(latestPhase4ReviewAuditLog) &&
    Boolean(latestPhase4OrderWindowAuditLog) &&
    Number.isFinite(estimatedNotional) &&
    estimatedNotional > 0 &&
    estimatedNotional <= phase4MaxNotionalValue &&
    allPhase4FinalConfirmations &&
    Boolean(phase4FinalPassword);
  const auditSeverityCounts = auditLogs.reduce<Record<string, number>>((counts, record) => {
    counts[record.severity] = (counts[record.severity] ?? 0) + 1;
    return counts;
  }, {});
  const mockAccounts = accounts.filter((account) => account.exchange_name === "mock");
  const exchangeReadOnlyAccounts = accounts.filter(
    (account) => account.exchange_name !== "mock" && !account.trading_enabled,
  );
  const activeReadOnlyAuthenticationAudit = auditLogs.find(
    (record) =>
      record.exchange_account_id === activeAccountId &&
      ["real.read_only.authentication.checked", "testnet.read_only.authentication.checked"].includes(record.action) &&
      !["ERROR", "WARNING"].includes(record.severity),
  );
  const auditHasErrors = (auditSeverityCounts.ERROR ?? 0) > 0;
  const liveOrderBoundaryIsLocked =
    !activeAccount ||
    activeAccount.exchange_name === "mock" ||
    activeAccount.account_mode !== "REAL" ||
    !activeAccount.trading_enabled;
  const preRealChecklist: PreRealChecklistItem[] = [
    {
      id: "session",
      title: "登录会话",
      detail: session.token ? `${session.username} / ${session.role}` : "账户检查前需要先登录。",
      required: true,
      status: session.token ? "pass" : "pending",
    },
    {
      id: "mock",
      title: "Mock 执行链路",
      detail:
        mockAccounts.length > 0
          ? `已有 ${mockAccounts.length} 个模拟账户。`
          : "先创建并运行 Mock 全链路，再进行交易所检查。",
      required: true,
      status: mockAccounts.length > 0 ? "pass" : "pending",
    },
    {
      id: "exchange-account",
      title: "只读交易所账户",
      detail:
        exchangeReadOnlyAccounts.length > 0
          ? `已有 ${exchangeReadOnlyAccounts.length} 个测试网或真实只读账户。`
          : "添加一个关闭交易开关的测试网或真实账户。",
      required: true,
      status: exchangeReadOnlyAccounts.length > 0 ? "pass" : "pending",
    },
    {
      id: "active-account",
      title: "已选择活动账户",
      detail: activeAccount
        ? `已选择 ${defaultAccountLabel(activeAccount.exchange_name, activeAccount.account_mode)}。`
        : "请在 API 与账户中选择账户。",
      required: true,
      status: activeAccount ? "pass" : "pending",
    },
    {
      id: "trading-flag",
      title: "交易开关保持关闭",
      detail: activeAccount
        ? activeAccount.trading_enabled
          ? "当前账户已允许交易，小额测试前应保持关闭。"
          : "平台侧当前账户保持只读。"
        : "选择账户后检查交易开关。",
      required: true,
      status: activeAccount ? (activeAccount.trading_enabled ? "fail" : "pass") : "pending",
    },
    {
      id: "secret",
      title: "密钥加密元数据",
      detail: selectedApiKeyMetadata.configured
        ? "Secret 已配置，且不会返回浏览器。"
        : "为选中账户保存 API Key 与 Secret。",
      required: true,
      status: selectedApiKeyMetadata.configured ? "pass" : "pending",
    },
    {
      id: "read-only-auth",
      title: "只读认证证据",
      detail: activeReadOnlyAuthenticationAudit
        ? `审计日志已记录 ${activeReadOnlyAuthenticationAudit.action}。`
        : "执行只读认证，并加载当前账户审计日志。",
      required: true,
      status: activeReadOnlyAuthenticationAudit ? "pass" : "pending",
    },
    {
      id: "audit-errors",
      title: "当前审计无错误",
      detail: auditHasErrors
        ? `当前加载视图中有 ${auditSeverityCounts.ERROR} 条 ERROR 审计记录。`
        : "当前加载视图没有 ERROR 记录。",
      required: true,
      status: auditHasErrors ? "fail" : "pass",
    },
    {
      id: "live-boundary",
      title: "真实下单边界",
      detail: liveOrderBoundaryIsLocked
        ? "当前界面仍锁定真实订单提交。"
        : "当前活动账户已启用真实交易。",
      required: true,
      status: liveOrderBoundaryIsLocked ? "pass" : "fail",
    },
    {
      id: "testnet-window",
      title: "测试网订单窗口审计",
      detail:
        approvalAuditLogs.length > 0
          ? `已加载 ${approvalAuditLogs.length} 条审批窗口审计记录。`
          : "可选：测试网订单演练前记录测试网订单窗口审批。",
      required: false,
      status: approvalAuditLogs.length > 0 ? "pass" : "warn",
    },
    {
      id: "phase4-review",
      title: "第四阶段小额资金复核",
      detail: latestPhase4ReviewAuditLog
        ? "真实小额资金复核审计已记录，但不授权下单。"
        : "可选：真实账户只读检查通过后，由超级管理员记录复核。",
      required: false,
      status: latestPhase4ReviewAuditLog ? "pass" : "warn",
    },
    {
      id: "phase4-real-window",
      title: "真实小额订单窗口",
      detail: latestPhase4OrderWindowAuditLog
        ? "真实小额订单窗口审批已作为仅审计证据记录。"
        : "可选终点：记录精确交易对、方向、数量、价格、名义金额和窗口时长。",
      required: false,
      status: latestPhase4OrderWindowAuditLog ? "pass" : "warn",
    },
    {
      id: "phase4-final-release",
      title: "第四阶段最终确认",
      detail: latestPhase4FinalReleaseAuditLog
        ? "最终确认审计已记录；平台仍未授权自动提交订单。"
        : "可选：复核和订单窗口审计存在后，记录小额测试前最终确认。",
      required: false,
      status: latestPhase4FinalReleaseAuditLog ? "pass" : "warn",
    },
  ];
  const requiredPreRealItems = preRealChecklist.filter((item) => item.required);
  const completedRequiredPreRealItems = requiredPreRealItems.filter((item) => item.status === "pass").length;
  const preRealReady = completedRequiredPreRealItems === requiredPreRealItems.length;
  const phase4AuditTrailReady =
    Boolean(latestPhase4ReviewAuditLog) &&
    Boolean(latestPhase4OrderWindowAuditLog) &&
    Boolean(latestPhase4FinalReleaseAuditLog);
  const finalReadinessMatrix = [
    {
      title: "必需安全检查",
      value: `${completedRequiredPreRealItems}/${requiredPreRealItems.length}`,
      detail: preRealReady ? "真实测试前必需检查已完成。" : "请先完成所有必需检查。",
      status: preRealReady ? "pass" : "blocked",
    },
    {
      title: "真实账户只读就绪",
      value: activePhase4Ready ? "通过" : "已锁定",
      detail: activePhase4Ready
        ? "选中的真实账户为只读，且未授权订单提交。"
        : "请加载真实 OKX 只读账户的就绪状态。",
      status: activePhase4Ready ? "pass" : "blocked",
    },
    {
      title: "审计链路",
      value: phase4AuditTrailReady ? "完成" : "未完成",
      detail: phase4AuditTrailReady
        ? "复核、订单窗口和最终确认审计均已记录。"
        : "小额资金测试前，记录第四阶段仅审计复核、窗口和最终确认。",
      status: phase4AuditTrailReady ? "pass" : "warn",
    },
    {
      title: "真实订单提交",
      value: "已锁定",
      detail: "当前 UI 仍不会提交真实交易所订单。",
      status: "pass",
    },
  ];
  const nextPreRealAction =
    preRealChecklist.find((item) => item.required && item.status !== "pass")?.detail ??
    "所有必需检查已完成。下一步是人工小额资金复核，不是自动真实下单。";
  const orderLocked = lockReasons.length > 0;
  const canRecordTestnetOrderWindow = testnetWindowReasons.length === 0;
  const gexbotProvider = marketDataProviders.find((provider) => provider.id === "gexbot");

  const marketRows = [
    { price: formatNumber(activeMarket.ask), amount: "0.184", side: "ask" },
    { price: formatNumber(activeMarket.ask - activeMarket.last * 0.0001), amount: "0.076", side: "ask" },
    { price: formatNumber(activeMarket.bid), amount: "0.214", side: "bid" },
    { price: formatNumber(activeMarket.bid - activeMarket.last * 0.00008), amount: "0.092", side: "bid" },
  ];

  async function createAccount() {
    if (!session.token) {
      appendApiLog("创建账户", false, "请先登录");
      return;
    }
    setApiBusy(true);
    try {
      const payload = await apiRequest(
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
      );
      const account = normalizeExchangeAccount(payload);
      if (!account) {
        throw new Error("创建账户返回缺少账户 ID，请刷新后重试");
      }
      setActiveExchange(account.exchange_name);
      setActiveAccountId(account.id);
      await refreshAccounts(account.id);
      appendApiLog("创建交易所账户", true, account);
    } catch (error) {
      appendApiLog("创建交易所账户", false, errorMessage(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function reloadAccounts() {
    if (!session.token) {
      appendApiLog("刷新账户", false, "请先登录");
      return;
    }
    setApiBusy(true);
    try {
      const selectedBeforeRefresh = activeAccountId;
      const nextAccounts = await refreshAccounts(selectedBeforeRefresh);
      const selectedAccountStillExists =
        selectedBeforeRefresh && nextAccounts.some((account) => account.id === selectedBeforeRefresh);
      appendApiLog("刷新账户", true, {
        account_count: nextAccounts.length,
        selected_account_id: selectedAccountStillExists ? selectedBeforeRefresh : null,
      });
    } catch (error) {
      appendApiLog("刷新账户", false, errorMessage(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function createReauthenticationToken(password: string) {
    const payload = (await apiRequest("POST", "/auth/reauthenticate", { password })) as {
      reauthentication_token?: string;
    };
    if (!payload.reauthentication_token) {
      throw new Error("缺少二次认证令牌");
    }
    return payload.reauthentication_token;
  }

  async function saveApiKey() {
    const selectedAccount = activeAccount;
    if (!selectedAccount) {
      appendApiLog("保存加密 API Key", false, "请先选择账户");
      return;
    }
    if (!selectedAccount.id) {
      appendApiLog("保存加密 API Key", false, "账户 ID 缺失，请刷新后重试");
      return;
    }
    if (selectedAccount.exchange_name === "okx" && !secretForm.passphrase) {
      appendApiLog("保存加密 API Key", false, "OKX 需要填写 Passphrase 口令");
      return;
    }
    setApiBusy(true);
    try {
      const reauthToken = await createReauthenticationToken(secretForm.password);
      const metadata = (await apiRequest(
        "POST",
        `/exchange-accounts/${selectedAccount.id}/api-key`,
        {
          api_key: secretForm.apiKey,
          api_secret: secretForm.apiSecret,
          passphrase: secretForm.passphrase || null,
        },
        200,
        { "X-Reauthentication-Token": reauthToken },
      )) as ApiKeyMetadata;
      setApiKeyMetadata(metadata);
      setSecretForm(emptySecretForm);
      appendApiLog("保存加密 API Key", true, metadata);
    } catch (error) {
      appendApiLog("保存加密 API Key", false, errorMessage(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function runReadOnlyCheck() {
    const selectedAccount = activeAccount;
    const selectedMetadata = selectedApiKeyMetadata;
    if (!selectedAccount) {
      appendApiLog("测试连接", false, "请先选择账户");
      return;
    }
    if (!selectedAccount.id) {
      appendApiLog("测试连接", false, "账户 ID 缺失，请刷新后重试");
      return;
    }
    if (selectedAccount.account_mode === "SIMULATION") {
      appendApiLog("测试连接", false, "模拟账户不使用交易所 API");
      return;
    }
    if (!selectedMetadata.configured) {
      appendApiLog("测试连接", false, "请先加密保存密钥；连接测试是可选步骤，不会阻止保存");
      return;
    }
    setApiBusy(true);
    try {
      const reauthToken = await createReauthenticationToken(secretForm.password);
      const checkPath =
        selectedAccount.account_mode === "REAL"
          ? "real-read-only-check"
          : "testnet-read-only-check";
      const result = await apiRequest(
        "POST",
        `/exchange-accounts/${selectedAccount.id}/${checkPath}`,
        undefined,
        200,
        { "X-Reauthentication-Token": reauthToken },
      );
      appendApiLog("测试连接", true, result);
    } catch (error) {
      appendApiLog("测试连接", false, errorMessage(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function deleteApiKey() {
    const selectedAccount = activeAccount;
    const selectedMetadata = selectedApiKeyMetadata;
    if (!selectedAccount) {
      appendApiLog("删除密钥", false, "请先选择账户");
      return;
    }
    if (!selectedAccount.id) {
      appendApiLog("删除密钥", false, "账户 ID 缺失，请刷新后重试");
      return;
    }
    if (!selectedMetadata.configured) {
      appendApiLog("删除密钥", false, "当前账户没有已保存的密钥");
      return;
    }
    const confirmed = window.confirm("确认删除该账户的加密密钥？删除后需要重新配置 API Key。");
    if (!confirmed) {
      appendApiLog("删除密钥", false, "用户取消删除");
      return;
    }
    setApiBusy(true);
    try {
      await apiRequest("DELETE", `/exchange-accounts/${selectedAccount.id}/api-key`, undefined, 204);
      setApiKeyMetadata(emptyMetadata);
      setSecretForm(emptySecretForm);
      appendApiLog("删除密钥", true, {
        exchange_account_id: selectedAccount.id,
        configured: false,
      });
      await refreshAccounts(selectedAccount.id).catch((refreshError) => {
        appendApiLog("删除密钥后刷新", false, errorMessage(refreshError));
      });
    } catch (error) {
      appendApiLog("删除密钥", false, errorMessage(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function deleteExchangeAccount() {
    const selectedAccount = activeAccount;
    if (!selectedAccount) {
      appendApiLog("删除账户", false, "请先选择账户");
      return;
    }
    if (!selectedAccount.id) {
      appendApiLog("删除账户", false, "账户 ID 缺失，请刷新后重试");
      return;
    }
    const confirmed = window.confirm(
      `确认删除账户「${selectedAccount.account_label}」？这只会删除平台内的账户记录和已保存密钥，不会删除交易所真实账户。`,
    );
    if (!confirmed) {
      appendApiLog("删除账户", false, "用户取消删除");
      return;
    }
    const deletedAccountId = selectedAccount.id;
    const deletedAccountLabel = selectedAccount.account_label;
    setApiBusy(true);
    try {
      await apiRequest("DELETE", `/exchange-accounts/${deletedAccountId}`, undefined, 204);
      setAccounts((currentAccounts) =>
        currentAccounts.filter((account) => account.id !== deletedAccountId),
      );
      if (activeAccountId === deletedAccountId) {
        clearApiAccountState();
      }
      appendApiLog("删除账户", true, {
        exchange_account_id: deletedAccountId,
        account_label: deletedAccountLabel,
      });
      await refreshAccounts().catch((refreshError) => {
        appendApiLog("删除账户后刷新", false, errorMessage(refreshError));
      });
    } catch (error) {
      appendApiLog("删除账户", false, errorMessage(error));
      await refreshAccounts().catch((refreshError) => {
        appendApiLog("删除失败后刷新", false, errorMessage(refreshError));
      });
    } finally {
      setApiBusy(false);
    }
  }

  async function loadOpenOrders() {
    const selectedAccount = activeAccount;
    if (!selectedAccount) {
      appendApiLog("加载当前委托", false, "请先选择 OKX 正式只读账户");
      return;
    }
    setOpenOrdersLoading(true);
    try {
      const result = (await apiRequest(
        "GET",
        `/exchange-accounts/${selectedAccount.id}/real-open-orders`,
      )) as { orders?: unknown };
      const nextOrders = Array.isArray(result.orders)
        ? result.orders.filter((item): item is RealOpenOrder => Boolean(item && typeof item === "object"))
        : [];
      setOpenOrders(nextOrders);
      setOpenOrdersLoadedAt(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
      appendApiLog("加载当前委托", true, { count: nextOrders.length, read_only: true });
    } catch (error) {
      setOpenOrders([]);
      setOpenOrdersLoadedAt("");
      appendApiLog("加载当前委托", false, errorMessage(error));
    } finally {
      setOpenOrdersLoading(false);
    }
  }

  async function loadBalances() {
    const selectedAccount = activeAccount;
    if (!selectedAccount) {
      appendApiLog("加载账户资产", false, "请先选择 OKX 正式只读账户");
      return;
    }
    setBalancesLoading(true);
    try {
      const result = (await apiRequest(
        "GET",
        `/exchange-accounts/${selectedAccount.id}/real-balances`,
      )) as { balances?: unknown };
      const nextBalances = Array.isArray(result.balances)
        ? result.balances.filter(
            (item): item is RealBalance =>
              Boolean(
                item &&
                  typeof item === "object" &&
                  "asset" in item &&
                  typeof item.asset === "string",
              ),
          )
        : [];
      setBalances(nextBalances);
      setBalancesLoadedAt(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
      appendApiLog("加载账户资产", true, { asset_count: nextBalances.length, read_only: true });
    } catch (error) {
      setBalances([]);
      setBalancesLoadedAt("");
      appendApiLog("加载账户资产", false, errorMessage(error));
    } finally {
      setBalancesLoading(false);
    }
  }

  async function loadGexbotTickers() {
    if (!session.token) {
      appendApiLog("加载 GEXBot 交易对", false, "请先登录");
      return;
    }
    setMarketDataBusy(true);
    try {
      const result = await apiRequest("GET", "/market-data/gexbot/tickers");
      setMarketDataResult(result);
      appendApiLog("加载 GEXBot 交易对", true, result);
    } catch (error) {
      appendApiLog("加载 GEXBot 交易对", false, errorMessage(error));
    } finally {
      setMarketDataBusy(false);
    }
  }

  async function loadGexbotDataset() {
    if (!session.token) {
      appendApiLog("加载 GEXBot 数据集", false, "请先登录");
      return;
    }
    const ticker = marketDataForm.ticker.trim().toUpperCase();
    const packageName = marketDataForm.package.trim().toLowerCase();
    const category = marketDataForm.category.trim().toLowerCase();
    if (!ticker || !category) {
      appendApiLog("加载 GEXBot 数据集", false, "需要填写交易对和分类");
      return;
    }
    setMarketDataBusy(true);
    try {
      const result = await apiRequest(
        "GET",
        `/market-data/gexbot/${encodeURIComponent(packageName)}/${encodeURIComponent(
          ticker,
        )}/${encodeURIComponent(category)}`,
      );
      setMarketDataResult(result);
      appendApiLog("加载 GEXBot 数据集", true, result);
    } catch (error) {
      appendApiLog("加载 GEXBot 数据集", false, errorMessage(error));
    } finally {
      setMarketDataBusy(false);
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
        createdFrom: "",
        createdTo: "",
        limit: current.limit,
      };
    });
  }

  async function loadAuditLogs(
    filterOverride: AuditFilters = auditFilters,
    preferredSelectedId = "",
  ) {
    if (!canViewAuditLogs) {
      appendApiLog("加载审计日志", false, "需要管理员权限");
      return;
    }
    setAuditBusy(true);
    try {
      const params = new URLSearchParams();
      if (filterOverride.userId.trim()) {
        params.set("user_id", filterOverride.userId.trim());
      }
      if (filterOverride.exchangeAccountId.trim()) {
        params.set("exchange_account_id", filterOverride.exchangeAccountId.trim());
      }
      if (filterOverride.action.trim()) {
        params.set("action", filterOverride.action.trim());
      }
      if (filterOverride.severity.trim()) {
        params.set("severity", filterOverride.severity.trim());
      }
      const createdFrom = toAuditQueryDateTime(filterOverride.createdFrom);
      const createdTo = toAuditQueryDateTime(filterOverride.createdTo);
      if (createdFrom) {
        params.set("created_from", createdFrom);
      }
      if (createdTo) {
        params.set("created_to", createdTo);
      }
      params.set("limit", filterOverride.limit || "50");

      const payload = await apiRequest("GET", `/admin/observability/audit-logs?${params}`);
      if (!Array.isArray(payload)) {
        throw new Error("audit log response is not an array");
      }
      const records = payload as AuditLogRecord[];
      setAuditLogs(records);
      const preferredRecord = records.find((record) => record.id === preferredSelectedId);
      setSelectedAuditLogId(preferredRecord?.id ?? records[0]?.id ?? "");
      setAuditLoadedAt(new Date().toLocaleString());
      appendApiLog("加载审计日志", true, {
        count: records.length,
        action: filterOverride.action || "*",
        severity: filterOverride.severity || "*",
        created_from: createdFrom || "*",
        created_to: createdTo || "*",
      });
    } catch (error) {
      appendApiLog("加载审计日志", false, errorMessage(error));
    } finally {
      setAuditBusy(false);
    }
  }

  function exportAuditReport() {
    if (!auditLogs.length) {
      appendApiLog("导出审计报告", false, "请先加载审计日志");
      return;
    }
    const generatedAt = new Date().toISOString();
    const report = {
      report_type: "audit_log_read_only_export",
      generated_at: generatedAt,
      generated_by: {
        user_id: session.userId,
        username: session.username,
        role: session.role,
      },
      filters: auditFilters,
      record_count: auditLogs.length,
      severity_counts: auditSeverityCounts,
      phase4_counts: {
        small_fund_reviews: phase4ReviewAuditLogs.length,
        real_order_windows: phase4OrderWindowAuditLogs.length,
        final_release_checks: phase4FinalReleaseAuditLogs.length,
      },
      records: auditLogs.map((record) => ({
        ...record,
        payload: sanitizeDetail(record.payload),
      })),
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `audit-report-${generatedAt.replace(/[:.]/g, "-")}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    appendApiLog("导出审计报告", true, {
      record_count: auditLogs.length,
      generated_at: generatedAt,
    });
  }

  function openOrderPreview() {
    setIsOrderPreviewOpen(true);
    setLastStatus(orderLocked ? "预览已锁定" : "预览就绪");
  }

  function selectAccountForTrading(account: ExchangeAccount) {
    setActiveExchange(account.exchange_name);
    setActiveAccountId(account.id);
    setBottomTab("balances");
    setLastStatus("账户已选择");
  }

  function focusAuditForAccount(account: ExchangeAccount) {
    const nextFilters = {
      ...auditFilters,
      exchangeAccountId: account.id,
      action:
        account.account_mode === "REAL"
          ? "real.read_only.authentication.checked"
          : "testnet.read_only.authentication.checked",
    };
    setAuditFilters(nextFilters);
    setBottomTab("audit");
    setLastStatus("审计筛选已就绪");
    if (canViewAuditLogs && session.token) {
      void loadAuditLogs(nextFilters);
    }
  }

  function focusTestnetApprovalAudits() {
    if (!activeAccount) {
      appendApiLog("定位测试网审批审计", false, "请先选择账户");
      return;
    }
    const nextFilters = {
      ...auditFilters,
      exchangeAccountId: activeAccount.id,
      action: "testnet.order_window.approval_recorded",
      severity: "",
    };
    setAuditFilters(nextFilters);
    setBottomTab("audit");
    setLastStatus("审批审计筛选已就绪");
    if (canViewAuditLogs && session.token) {
      void loadAuditLogs(nextFilters);
    }
  }

  function focusPhase4ReviewAudits() {
    if (!activeAccount) {
      appendApiLog("定位第四阶段复核审计", false, "请先选择账户");
      return;
    }
    const nextFilters = {
      ...auditFilters,
      exchangeAccountId: activeAccount.id,
      action: "real.small_fund.review_recorded",
      severity: "",
    };
    setAuditFilters(nextFilters);
    setBottomTab("audit");
    setLastStatus("第四阶段复核审计筛选已就绪");
    if (canViewAuditLogs && session.token) {
      void loadAuditLogs(nextFilters);
    }
  }

  function focusPhase4OrderWindowAudits() {
    if (!activeAccount) {
      appendApiLog("定位第四阶段真实订单窗口审计", false, "请先选择账户");
      return;
    }
    const nextFilters = {
      ...auditFilters,
      exchangeAccountId: activeAccount.id,
      action: "real.small_fund.order_window.approval_recorded",
      severity: "",
    };
    setAuditFilters(nextFilters);
    setBottomTab("audit");
    setLastStatus("第四阶段订单窗口审计筛选已就绪");
    if (canViewAuditLogs && session.token) {
      void loadAuditLogs(nextFilters);
    }
  }

  function focusPhase4FinalReleaseAudits() {
    if (!activeAccount) {
      appendApiLog("定位第四阶段最终确认审计", false, "请先选择账户");
      return;
    }
    const nextFilters = {
      ...auditFilters,
      exchangeAccountId: activeAccount.id,
      action: "real.small_fund.final_release_check_recorded",
      severity: "",
    };
    setAuditFilters(nextFilters);
    setBottomTab("audit");
    setLastStatus("第四阶段最终审计筛选已就绪");
    if (canViewAuditLogs && session.token) {
      void loadAuditLogs(nextFilters);
    }
  }

  async function loadPhase4Readiness() {
    if (!activeAccount) {
      appendApiLog("加载第四阶段就绪状态", false, "请先选择真实 OKX 账户");
      return;
    }
    setApiBusy(true);
    try {
      const report = (await apiRequest(
        "GET",
        `/exchange-accounts/${activeAccount.id}/phase4-readiness`,
      )) as Phase4ReadinessReport;
      setPhase4Readiness(report);
      appendApiLog("加载第四阶段就绪状态", report.overall_status === "PASS", report);
    } catch (error) {
      setPhase4Readiness(null);
      appendApiLog("加载第四阶段就绪状态", false, errorMessage(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function recordPhase4SmallFundReview() {
    if (!activeAccount) {
      appendApiLog("记录第四阶段复核", false, "请先选择真实 OKX 账户");
      return;
    }
    if (!phase4ReviewPassword) {
      appendApiLog("记录第四阶段复核", false, "需要当前登录密码");
      return;
    }
    setApiBusy(true);
    try {
      const reauthToken = await createReauthenticationToken(phase4ReviewPassword);
      const result = await apiRequest(
        "POST",
        `/exchange-accounts/${activeAccount.id}/phase4-small-fund-reviews`,
        {
          max_notional: phase4MaxNotionalValue,
          acknowledgement: phase4SmallFundReviewAck,
        },
        200,
        { "X-Reauthentication-Token": reauthToken },
      );
      setPhase4ReviewPassword("");
      appendApiLog("记录第四阶段复核", true, result);
      const reviewAuditLogId =
        result && typeof result === "object" && "audit_log_id" in result
          ? String(result.audit_log_id)
          : "";
      const nextFilters = {
        ...auditFilters,
        exchangeAccountId: activeAccount.id,
        action: "real.small_fund.review_recorded",
        severity: "",
      };
      setAuditFilters(nextFilters);
      setBottomTab("audit");
      if (canViewAuditLogs) {
        await loadAuditLogs(nextFilters, reviewAuditLogId);
      }
    } catch (error) {
      appendApiLog("记录第四阶段复核", false, errorMessage(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function recordPhase4OrderWindowApproval() {
    if (!activeAccount || !canRecordPhase4OrderWindow) {
      return;
    }
    if (!phase4OrderWindowPassword) {
      appendApiLog("记录第四阶段真实订单窗口", false, "需要当前登录密码");
      return;
    }
    setApiBusy(true);
    try {
      const reauthToken = await createReauthenticationToken(phase4OrderWindowPassword);
      const result = await apiRequest(
        "POST",
        `/exchange-accounts/${activeAccount.id}/phase4-small-fund-order-window-approvals`,
        {
          symbol: normalizedPreviewSymbol,
          side: orderSide,
          max_quantity: parsedQuantity,
          limit_price: parsedPrice,
          max_notional: estimatedNotional,
          duration_minutes: phase4OrderWindowDurationValue,
          acknowledgement: phase4SmallFundOrderWindowAck,
        },
        200,
        { "X-Reauthentication-Token": reauthToken },
      );
      setPhase4OrderWindowPassword("");
      appendApiLog("记录第四阶段真实订单窗口", true, result);
      const approvalAuditLogId =
        result && typeof result === "object" && "audit_log_id" in result
          ? String(result.audit_log_id)
          : "";
      const nextFilters = {
        ...auditFilters,
        exchangeAccountId: activeAccount.id,
        action: "real.small_fund.order_window.approval_recorded",
        severity: "",
      };
      setAuditFilters(nextFilters);
      setBottomTab("audit");
      if (canViewAuditLogs) {
        await loadAuditLogs(nextFilters, approvalAuditLogId);
      }
    } catch (error) {
      appendApiLog("记录第四阶段真实订单窗口", false, errorMessage(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function recordPhase4FinalReleaseCheck() {
    if (!activeAccount || !canRecordPhase4FinalReleaseCheck) {
      return;
    }
    if (!phase4FinalPassword) {
      appendApiLog("记录第四阶段最终确认", false, "需要当前登录密码");
      return;
    }
    setApiBusy(true);
    try {
      const reauthToken = await createReauthenticationToken(phase4FinalPassword);
      const result = await apiRequest(
        "POST",
        `/exchange-accounts/${activeAccount.id}/phase4-final-release-checks`,
        {
          max_notional: estimatedNotional,
          dedicated_account_confirmed: phase4FinalConfirmations.dedicatedAccount,
          account_empty_confirmed: phase4FinalConfirmations.accountEmpty,
          withdrawals_disabled_confirmed: phase4FinalConfirmations.withdrawalsDisabled,
          delete_api_key_after_test_confirmed:
            phase4FinalConfirmations.deleteApiKeyAfterTest,
          first_order_stop_review_confirmed: phase4FinalConfirmations.firstOrderStopReview,
          no_live_order_submission_confirmed: phase4FinalConfirmations.noLiveOrderSubmission,
          acknowledgement: phase4FinalReleaseCheckAck,
        },
        200,
        { "X-Reauthentication-Token": reauthToken },
      );
      setPhase4FinalPassword("");
      appendApiLog("记录第四阶段最终确认", true, result);
      const finalAuditLogId =
        result && typeof result === "object" && "audit_log_id" in result
          ? String(result.audit_log_id)
          : "";
      const nextFilters = {
        ...auditFilters,
        exchangeAccountId: activeAccount.id,
        action: "real.small_fund.final_release_check_recorded",
        severity: "",
      };
      setAuditFilters(nextFilters);
      setBottomTab("audit");
      if (canViewAuditLogs) {
        await loadAuditLogs(nextFilters, finalAuditLogId);
      }
    } catch (error) {
      appendApiLog("记录第四阶段最终确认", false, errorMessage(error));
    } finally {
      setApiBusy(false);
    }
  }

  function confirmOrderPreview() {
    if (orderLocked) {
      return;
    }
    appendApiLog("下单预览已确认", true, orderPreviewPayload);
    setBottomTab("history");
    setIsOrderPreviewOpen(false);
  }

  async function recordTestnetOrderWindowApproval() {
    if (!activeAccount || !canRecordTestnetOrderWindow) {
      return;
    }
    if (!orderApprovalPassword) {
      appendApiLog("记录测试网订单窗口", false, "需要当前登录密码");
      return;
    }
    setApiBusy(true);
    try {
      const reauthToken = await createReauthenticationToken(orderApprovalPassword);
      const result = await apiRequest(
        "POST",
        `/exchange-accounts/${activeAccount.id}/testnet-order-window-approvals`,
        {
          symbol: normalizedPreviewSymbol,
          side: orderSide,
          max_quantity: parsedQuantity,
          max_notional: estimatedNotional,
          duration_minutes: 5,
          acknowledgement: testnetOrderWindowApprovalAck,
        },
        200,
        { "X-Reauthentication-Token": reauthToken },
      );
      setOrderApprovalPassword("");
      appendApiLog("记录测试网订单窗口", true, result);
      const approvalAuditLogId =
        result && typeof result === "object" && "audit_log_id" in result
          ? String(result.audit_log_id)
          : "";
      const nextFilters = {
        ...auditFilters,
        exchangeAccountId: activeAccount.id,
        action: "testnet.order_window.approval_recorded",
        severity: "",
      };
      setAuditFilters(nextFilters);
      setBottomTab("audit");
      setIsOrderPreviewOpen(false);
      if (canViewAuditLogs) {
        await loadAuditLogs(nextFilters, approvalAuditLogId);
      }
    } catch (error) {
      appendApiLog("记录测试网订单窗口", false, errorMessage(error));
    } finally {
      setApiBusy(false);
    }
  }

  function focusAuditForCurrentAccount() {
    if (!activeAccount) {
      appendApiLog("定位审计日志", false, "请先选择账户");
      return;
    }
    focusAuditForAccount(activeAccount);
  }

  if (!sessionChecked) {
    return (
      <main className="trade-auth-loading">
        <section>
          <span>会话检查</span>
          <h1>正在恢复交易会话</h1>
          <p>登录会话确认完成后会进入交易终端。</p>
        </section>
      </main>
    );
  }

  if (!session.token) {
    return (
      <main className="trade-auth-loading">
        <section>
          <span>需要认证</span>
          <h1>需要登录</h1>
          <p>正在跳转到登录页面。</p>
        </section>
      </main>
    );
  }

  return (
    <main className={`trade-terminal trade-workspace-${activeWorkspace}`}>
      <aside className="trade-sidebar">
        <a className="trade-brand" href="/trade">
          <span>CT</span>
          <strong>交易工作台</strong>
        </a>
        <nav>
          <a className={activeWorkspace === "terminal" ? "active" : ""} href="/trade#terminal">
            交易终端
          </a>
          <a className={activeWorkspace === "portfolio" ? "active" : ""} href="/trade#portfolio">
            资产概览
          </a>
          <a className={activeWorkspace === "api-management" ? "active" : ""} href="/trade#api-management">
            API 与账户
          </a>
          <a className={activeWorkspace === "risk" ? "active" : ""} href="/trade#risk">
            风控中心
          </a>
          <a className={activeWorkspace === "market-data" ? "active" : ""} href="/trade#market-data">
            市场数据
          </a>
          <a className={activeWorkspace === "audit" ? "active" : ""} href="/trade#audit">
            审计中心
          </a>
          <a className={activeWorkspace === "small-fund" ? "active" : ""} href="/trade#phase4-small-fund-review">
            小额测试闸门
          </a>
          {session.role === "super_admin" && <a href="/">管理控制台</a>}
          <a href="/login">切换账户</a>
        </nav>
        <div className="trade-guardrail">
          <span>运行边界</span>
          <strong>禁止实盘下单</strong>
          <p>实盘执行仍被闸门拦截。当前终端仅用于预览订单、验证账户和记录审批。</p>
        </div>
      </aside>

      <section className="trade-main">
        <header className="trade-topbar">
          <div>
            <span className="trade-kicker">统一交易工作区</span>
            <h1>{activeWorkspace === "terminal" ? `${activeSymbol} 交易终端` : activeWorkspaceLabel}</h1>
          </div>
          <div className="trade-topbar-actions">
            <a href="/trade#api-management">添加 API</a>
            <a href="/trade#audit">审计</a>
            {session.role === "super_admin" ? <a href="/">控制台</a> : null}
          </div>
          <div className="trade-user-pill">
            <span>{session.token ? session.username : "未登录"}</span>
            <strong>{session.role || "访客"}</strong>
          </div>
        </header>

        <section className="trade-command-center" id="portfolio" data-workspace="portfolio">
          <article>
            <span>工作区模式</span>
            <strong>模拟 / 测试网 / 真实账户只读</strong>
            <p>真实执行必须通过超级管理员复核、审计留痕和订单窗口审批。</p>
          </article>
          <article>
            <span>账户</span>
            <strong>{accounts.length}</strong>
            <p>
              SIM {accountModeSummary.simulation} / TESTNET {accountModeSummary.testnet} / REAL {accountModeSummary.real}
            </p>
          </article>
          <article>
            <span>当前交易所</span>
            <strong>{activeExchangeProfile.venue}</strong>
            <p>当前交易所有 {activeExchangeAccounts.length} 个账户。</p>
          </article>
          <article>
            <span>执行边界</span>
            <strong>{accountModeSummary.tradingEnabled > 0 ? "需要复核" : "已锁定"}</strong>
            <p>{accountModeSummary.tradingEnabled} 个账户当前启用了交易标记。</p>
          </article>
        </section>

        <section className="trade-market-strip" data-workspace="terminal">
          {exchanges.map((exchange) => {
            const accountCount = accounts.filter((account) => account.exchange_name === exchange).length;
            return (
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
                <strong>{exchangeProfiles[exchange].label}</strong>
                <span>{accountCount} 个账户 / {exchangeProfiles[exchange].route}</span>
              </button>
            );
          })}
          <details className="trade-symbol-picker">
            <summary>
              <span>交易对</span>
              <strong>{activeSymbol}</strong>
            </summary>
            <div className="trade-symbol-menu">
              <input
                aria-label="搜索交易对"
                placeholder="搜索 BTC、ETH、USDT"
                value={symbolSearch}
                onChange={(event) => setSymbolSearch(event.target.value)}
              />
              {favoritePinnedSymbols.length > 0 && (
                <div className="trade-symbol-pinned" aria-label="常用交易对">
                  {favoritePinnedSymbols.map((symbol) => (
                    <button
                      className={symbol === activeSymbol ? "active" : ""}
                      key={symbol}
                      onClick={() => setActiveSymbol(symbol)}
                      type="button"
                    >
                      ★ {symbol}
                    </button>
                  ))}
                </div>
              )}
              <div className="trade-symbol-list">
                {filteredSymbols.map((symbol) => {
                  const snapshot = marketSnapshots[symbol] ?? marketSnapshots["BTC/USDT"];
                  const isFavorite = favoriteSymbolSet.has(symbol);
                  return (
                    <div className={symbol === activeSymbol ? "trade-symbol-row active" : "trade-symbol-row"} key={symbol}>
                      <button
                        className="trade-symbol-star"
                        onClick={(event) => {
                          event.preventDefault();
                          toggleFavoriteSymbol(symbol);
                        }}
                        title={isFavorite ? "取消置顶" : "星标置顶"}
                        type="button"
                      >
                        {isFavorite ? "★" : "☆"}
                      </button>
                      <button className="trade-symbol-main" onClick={() => setActiveSymbol(symbol)} type="button">
                        <strong>{symbol}</strong>
                        <span>
                          {formatNumber(snapshot.last)} · {snapshot.change}
                        </span>
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          </details>
        </section>

        <section className="trade-layout-grid" data-workspace="terminal">
          <div className="trade-card trade-chart">
            <div className="trade-card-head">
              <div>
                <span>行情图</span>
                <strong>
                  {activeExchangeProfile.label} / {activeSymbol}
                </strong>
              </div>
              <em>
                {formatNumber(liveMarketPrice ?? activeMarket.last)} USDT {activeMarket.change}
              </em>
            </div>
            <LiveMarketChart
              apiRoot={apiRoot}
              exchange={activeExchange}
              onPriceUpdate={setLiveMarketPrice}
              symbol={activeSymbol}
              token={session.token}
            />
            <div className="trade-exchange-window">
              <div>
                <span>交易所窗口</span>
                <strong>{activeExchangeProfile.venue}</strong>
              </div>
              <div className="trade-window-status">
                <span>{activeExchangeProfile.label}</span>
                <strong>{activeAccountHealth}</strong>
              </div>
              <dl>
                <div>
                  <dt>账户</dt>
                  <dd>{activeAccount?.account_label ?? "未选择"}</dd>
                </div>
                <div>
                  <dt>模式</dt>
                <dd>{safeAccountModeLabel(activeAccount?.account_mode)}</dd>
                </div>
                <div>
                  <dt>路由</dt>
                  <dd>{activeExchangeProfile.route}</dd>
                </div>
                <div>
                  <dt>密钥</dt>
                  <dd>
                    {apiMetadataLoading
                      ? "读取中"
                      : selectedApiKeyMetadata.configured
                        ? "已配置"
                        : "未配置"}
                  </dd>
                </div>
              </dl>
              <div className="trade-window-route">
                <span>订单绑定</span>
                <strong>{selectedAccountRoute}</strong>
              </div>
              <p>{activeExchangeProfile.window}</p>
            </div>
          </div>

          <div className="trade-card trade-orderbook">
            <div className="trade-card-head">
              <strong>订单簿</strong>
              <span>只读</span>
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
              <strong>下单面板</strong>
              <span>{resultLabels[lastStatus] ?? lastStatus}</span>
            </div>
            <div className="trade-ticket-mode" aria-label="订单类型选择">
              <button
                className={orderForm.orderType === "MARKET" ? "active" : ""}
                onClick={() => setOrderForm((current) => ({ ...current, orderType: "MARKET" }))}
              >
                市价
              </button>
              <button
                className={orderForm.orderType === "LIMIT" ? "active" : ""}
                onClick={() => setOrderForm((current) => ({ ...current, orderType: "LIMIT" }))}
              >
                限价
              </button>
            </div>
            <div className="trade-side-switch" aria-label="买卖方向选择">
              <button
                className={orderSide === "BUY" ? "buy active" : "buy"}
                onClick={() => setOrderSide("BUY")}
              >
                买入
              </button>
              <button
                className={orderSide === "SELL" ? "sell active" : "sell"}
                onClick={() => setOrderSide("SELL")}
              >
                卖出
              </button>
            </div>
            <label>
              价格
              <input
                inputMode="decimal"
                readOnly={orderForm.orderType === "MARKET"}
                value={
                  orderForm.orderType === "MARKET"
                    ? `市价 / ${formatNumber(activeMarket.last)}`
                    : orderForm.price
                }
                onChange={(event) =>
                  setOrderForm((current) => ({ ...current, price: event.target.value }))
                }
              />
            </label>
            <label>
              数量
              <input
                inputMode="decimal"
                value={orderForm.quantity}
                onChange={(event) =>
                  setOrderForm((current) => ({ ...current, quantity: event.target.value }))
                }
              />
            </label>
            <label>
              账户
              <select
                value={activeAccountId}
                onChange={(event) => setActiveAccountId(event.target.value)}
              >
                {exchangeAccounts.length === 0 ? (
                  <option value="">暂无 {activeExchangeProfile.label} 账户</option>
                ) : (
                  exchangeAccounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.account_label} / {safeAccountModeLabel(account.account_mode)}
                    </option>
                  ))
                )}
              </select>
            </label>
            <div className="trade-ticket-account">
              <span>当前路由</span>
              <strong>{selectedAccountRoute}</strong>
            </div>
            <div className="trade-order-preview">
              <div>
                <span>方向</span>
                <strong className={orderSide === "BUY" ? "preview-buy" : "preview-sell"}>
                  {orderSideLabels[orderSide]}
                </strong>
              </div>
              <div>
                <span>类型</span>
                <strong>{orderTypeLabels[orderForm.orderType]}</strong>
              </div>
              <div>
                <span>预估价格</span>
                <strong>{formatNumber(referencePrice)} USDT</strong>
              </div>
              <div>
                <span>预估名义金额</span>
                <strong>{formatNumber(estimatedNotional)} USDT</strong>
              </div>
            </div>
            <div className="trade-route-panel">
              <span>客户端订单 ID 预览</span>
              <code>{clientOrderIdPreview}</code>
            </div>
            <button className="trade-submit" onClick={openOrderPreview}>
              查看下单预览
            </button>
            {lockReasons.length === 0 ? (
              <p>Mock 预览路由已开放。当前页面仍不会提交真实订单。</p>
            ) : (
              <ul className="trade-lock-list">
                {lockReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="trade-desk-grid" id="risk" data-workspace="risk">
          <article className="trade-desk-panel">
            <div className="trade-card-head">
              <div>
                <span>账户路由</span>
                <strong>账户选择 {"->"} 交易所窗口 {"->"} 下单预览</strong>
              </div>
              <em>{selectedAccountRoute}</em>
            </div>
            <div className="trade-route-steps">
              <span className={activeAccount ? "done" : ""}>1. 选择账户</span>
              <span className={selectedApiKeyMetadata.configured ? "done" : ""}>2. 验证密钥</span>
              <span className={estimatedNotional > 0 ? "done" : ""}>3. 生成预览</span>
              <span className={lockReasons.length === 0 ? "done" : ""}>4. 安全闸门</span>
            </div>
          </article>
          <article className="trade-desk-panel">
            <div className="trade-card-head">
              <div>
                <span>风控闸门</span>
                <strong>{lockReasons.length === 0 ? "预览开放" : "已拦截"}</strong>
              </div>
              <em>{lockReasons.length} 条原因</em>
            </div>
            <ul className="trade-risk-chips">
              {(lockReasons.length ? lockReasons : ["Mock 预览路由可用"]).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </article>
        </section>

        <section className="trade-market-data-panel" id="market-data" data-workspace="market-data">
          <div className="trade-card-head">
            <div>
              <span>市场数据服务</span>
              <strong>GEXBot 只读数据源</strong>
            </div>
            <button
              className="trade-secondary-button"
              onClick={refreshMarketDataProviders}
              disabled={!session.token || marketDataBusy}
            >
              刷新
            </button>
          </div>
          <div className="trade-market-data-grid">
            <article className="trade-market-data-status">
              <span>服务商</span>
              <strong>{gexbotProvider?.name ?? "GEXBot"}</strong>
              <p>
                {gexbotProvider?.configured
                  ? "后端已配置 API Key，可读取授权数据集。"
                  : "后端未配置 API Key，仅可读取公开或本地可用数据。"}
              </p>
              <dl>
                <div>
                  <dt>模式</dt>
                  <dd>只读</dd>
                </div>
                <div>
                  <dt>接口</dt>
                  <dd>{gexbotProvider?.supports?.join(" / ") ?? "交易对 / 经典数据 / 状态"}</dd>
                </div>
              </dl>
            </article>
            <article className="trade-market-data-query">
              <label>
                代码
                <input
                  value={marketDataForm.ticker}
                  onChange={(event) =>
                    setMarketDataForm((current) => ({
                      ...current,
                      ticker: event.target.value,
                    }))
                  }
                />
              </label>
              <label>
                数据包
                <select
                  value={marketDataForm.package}
                  onChange={(event) =>
                    setMarketDataForm((current) => ({
                      ...current,
                      package: event.target.value,
                    }))
                  }
                >
                  <option value="classic">经典数据</option>
                  <option value="state">状态数据</option>
                </select>
              </label>
              <label>
                分类
                <input
                  value={marketDataForm.category}
                  onChange={(event) =>
                    setMarketDataForm((current) => ({
                      ...current,
                      category: event.target.value,
                    }))
                  }
                />
              </label>
              <div className="trade-action-row">
                <button
                  className="trade-secondary-button"
                  onClick={loadGexbotTickers}
                  disabled={!session.token || marketDataBusy}
                >
                  读取标的列表
                </button>
                <button
                  className="trade-submit compact"
                  onClick={loadGexbotDataset}
                  disabled={!session.token || marketDataBusy}
                >
                  读取数据集
                </button>
              </div>
            </article>
          </div>
          <div className="trade-market-data-result">
            <div>
              <strong>最近市场数据结果</strong>
              <span>{marketDataBusy ? "读取中" : marketDataResult ? "已加载" : "待执行"}</span>
            </div>
            <pre>{marketDataResult ? prettyJson(marketDataResult) : "暂无数据"}</pre>
          </div>
        </section>

        <section className="trade-api-manager" id="api-management" data-workspace="api-management">
          <div className="trade-card-head">
            <div>
              <span>API 管理</span>
              <strong>统一添加 / 密钥状态 / 测试连接</strong>
            </div>
            <button
              className="trade-secondary-button"
              onClick={reloadAccounts}
              disabled={!session.token || apiBusy}
            >
              刷新
            </button>
          </div>

          <div className="trade-api-manager-grid">
            <div className="trade-api-panel">
              <h2>已添加账户</h2>
              <div className="trade-account-list">
                {exchangeAccounts.length === 0 ? (
                  <p className="trade-muted">当前交易所还没有账户。填写右侧信息后可创建账户并保存密钥。</p>
                ) : (
                  exchangeAccounts.map((account) => (
                    <article
                      className={
                        account.id === activeAccountId
                          ? "trade-account-option selected"
                          : "trade-account-option"
                      }
                      key={account.id}
                      role="button"
                      tabIndex={0}
                      onClick={(event) => {
                        if ((event.target as HTMLElement).closest("button")) {
                          return;
                        }
                        selectAccountForTrading(account);
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          selectAccountForTrading(account);
                        }
                      }}
                    >
                      <div>
                        <strong>{account.account_label}</strong>
                        <span>
                          {safeAccountModeLabel(account.account_mode)} / {account.trading_enabled ? "交易已开启" : "只读"}
                        </span>
                      </div>
                      <div className="trade-account-actions">
                        <button onClick={() => selectAccountForTrading(account)}>用于下单面板</button>
                        <button
                          onClick={() => {
                            selectAccountForTrading(account);
                            setBottomTab("balances");
                          }}
                        >
                          交易所窗口
                        </button>
                        <button
                          onClick={() => {
                            selectAccountForTrading(account);
                            focusAuditForAccount(account);
                          }}
                        >
                          审计
                        </button>
                      </div>
                    </article>
                  ))
                )}
              </div>
              <dl className="trade-account-meta">
                <div>
                  <dt>已选择</dt>
                  <dd>{activeAccount?.account_label ?? "-"}</dd>
                </div>
                <div>
                  <dt>密钥</dt>
                  <dd>
                    {apiMetadataLoading
                      ? "读取中"
                      : selectedApiKeyMetadata.configured
                        ? "已配置"
                        : "未配置"}
                  </dd>
                </div>
                <div>
                  <dt>Passphrase 口令</dt>
                  <dd>{selectedApiKeyMetadata.has_passphrase ? "已配置" : "未配置"}</dd>
                </div>
              </dl>
            </div>

            <div className="trade-api-panel">
              <h2>添加交易所账户</h2>
              <p className="trade-muted">先选择交易所和模式，创建账户后再保存密钥。保存密钥不会强制执行连接测试。</p>
              <div className="trade-form-grid">
                <label>
                  交易所
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
                  账户模式
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
                    <option value="SIMULATION">模拟</option>
                    <option value="TESTNET">测试网只读</option>
                    <option value="REAL">真实账户只读</option>
                  </select>
                </label>
                <label>
                  账户标签
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
                创建账户
              </button>
            </div>

            <div className="trade-api-panel">
              <h2>API Key 与连接测试</h2>
              <p className="trade-muted">连接测试是独立功能。正式环境建议先测试连接，再用于小额资金人工复核。</p>
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
                  Passphrase 口令
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
                  当前登录密码
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
                  加密保存密钥
                </button>
                <button
                  className="trade-submit compact"
                  onClick={runReadOnlyCheck}
                  disabled={!activeAccount || !selectedApiKeyMetadata.configured || !secretForm.password || apiBusy}
                >
                  测试连接
                </button>
                <button
                  className="trade-danger-button span-2"
                  onClick={deleteApiKey}
                  disabled={!activeAccount || !selectedApiKeyMetadata.configured || apiBusy}
                >
                  删除密钥（保留账户）
                </button>
                <button
                  className="trade-danger-button span-2"
                  onClick={deleteExchangeAccount}
                  disabled={!activeAccount || apiBusy}
                >
                  删除账户
                </button>
              </div>
            </div>
          </div>

          <div className="trade-action-log" aria-label="API 管理执行日志">
            {apiLogs.length === 0 ? (
              <p className="trade-muted">暂无 API 管理操作记录。</p>
            ) : (
              apiLogs.map((log) => (
                <article key={log.id}>
                  <div>
                    <strong>{log.title}</strong>
                    <span className={log.ok ? "log-ok" : "log-fail"}>{log.ok ? "通过" : "失败"}</span>
                  </div>
                  <pre>{prettyJson(log.detail)}</pre>
                </article>
              ))
            )}
          </div>
        </section>

        <section className="trade-preflight-card" id="pre-real-checklist" data-workspace="small-fund">
          <div className="trade-preflight-head">
            <div>
              <span>实盘前安全清单</span>
              <strong>小额资金测试前置检查</strong>
              <p>
                只汇总登录、账户、密钥、只读认证和审计证据。此清单不会开启真实交易，也不会发送订单。
              </p>
            </div>
            <div className="trade-preflight-status">
              <span className={preRealReady ? "ready" : "blocked"}>
                {preRealReady ? "可人工复核" : "已锁定"}
              </span>
              <strong>
                {completedRequiredPreRealItems}/{requiredPreRealItems.length}
              </strong>
              <small>必检项</small>
            </div>
          </div>
          <div className="trade-preflight-actions">
            <button
              className="trade-ghost-button"
              onClick={reloadAccounts}
              disabled={!session.token || apiBusy}
            >
              刷新账户
            </button>
            <button
              className="trade-ghost-button"
              onClick={() => activeAccount && focusAuditForAccount(activeAccount)}
              disabled={!activeAccount || !canViewAuditLogs || auditBusy}
            >
              加载当前审计
            </button>
            <button
              className="trade-ghost-button"
              onClick={focusTestnetApprovalAudits}
              disabled={!canViewAuditLogs || auditBusy}
            >
              加载测试网窗口
            </button>
          </div>
          <div className="trade-checklist-grid">
            {preRealChecklist.map((item) => (
              <article className={`trade-check-item ${item.status}`} key={item.id}>
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.required ? "必检" : "可选"}</span>
                </div>
                <p>{item.detail}</p>
                <b>{resultLabels[item.status.toUpperCase()] ?? item.status.toUpperCase()}</b>
              </article>
            ))}
          </div>
          <div className={preRealReady ? "trade-next-action ready" : "trade-next-action"}>
            <span>下一步</span>
            <strong>{nextPreRealAction}</strong>
          </div>
        </section>

        <section className="trade-final-readiness-card" id="small-fund-final-readiness" data-workspace="small-fund">
          <div className="trade-section-heading">
            <div>
              <span>最终闸门</span>
              <h2>小额资金测试就绪状态</h2>
              <p>
                第四阶段小额资金测试前的汇总视图。即使此面板通过，当前版本仍保持真实订单提交锁定。
              </p>
            </div>
          </div>
          <div className="trade-final-readiness-grid">
            {finalReadinessMatrix.map((item) => (
              <article className={`trade-final-readiness-item ${item.status}`} key={item.title}>
                <span>{item.title}</span>
                <strong>{item.value}</strong>
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="trade-phase4-card" id="phase4-small-fund-review" data-workspace="small-fund">
          <div className="trade-phase4-head">
            <div>
              <span>第四阶段控制</span>
              <strong>小额资金复核审计</strong>
              <p>
                为选中的真实 OKX 账户记录超级管理员复核。此操作不会启用交易、授权下单或暴露 API Secret。
              </p>
            </div>
            <div className={activePhase4Ready ? "phase4-status ready" : "phase4-status blocked"}>
              <span>{activePhase4Ready ? "准备就绪" : "准备未完成"}</span>
              <strong>{latestPhase4ReviewAuditLog ? "复核已记录" : "无复核审计"}</strong>
            </div>
          </div>
          <div className="trade-phase4-grid">
            <label>
              <span>最大名义金额</span>
              <input
                inputMode="decimal"
                value={phase4MaxNotional}
                onChange={(event) => setPhase4MaxNotional(event.target.value)}
                placeholder="25"
              />
            </label>
            <label>
              <span>当前登录密码</span>
              <input
                type="password"
                value={phase4ReviewPassword}
                onChange={(event) => setPhase4ReviewPassword(event.target.value)}
                placeholder="用于重新认证"
              />
            </label>
            <button
              className="trade-secondary-button"
              onClick={loadPhase4Readiness}
              disabled={!activeAccount || apiBusy}
            >
              加载就绪状态
            </button>
            <button
              className="trade-submit compact"
              onClick={recordPhase4SmallFundReview}
              disabled={!canRecordPhase4SmallFundReview || apiBusy}
            >
              记录复核审计
            </button>
          </div>
          <div className="trade-phase4-actions">
            <button
              className="trade-ghost-button"
              onClick={focusPhase4ReviewAudits}
              disabled={!activeAccount || !canViewAuditLogs || auditBusy}
            >
              加载复核审计
            </button>
            <span>
              必需确认码：<strong>{phase4SmallFundReviewAck}</strong>
            </span>
          </div>
          {phase4Readiness ? (
            <div className="trade-readiness-list">
              {phase4Readiness.checks.map((check) => (
                <article
                  className={`trade-readiness-check ${
                    check.status === "PASS" ? "pass" : "blocked"
                  }`}
                  key={check.name}
                >
                  <div>
                    <strong>{check.name}</strong>
                    <span>{resultLabels[check.status] ?? check.status}</span>
                  </div>
                  <p>{check.detail}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="trade-muted">
              选择真实 OKX 账户并加载就绪状态后，才能记录复核审计。
            </p>
          )}
        </section>

        <section className="trade-phase4-card" id="phase4-real-order-window" data-workspace="small-fund">
          <div className="trade-phase4-head">
            <div>
              <span>第四阶段控制</span>
              <strong>真实小额订单窗口</strong>
              <p>
                将精确的真实订单窗口审批记录为 append-only 审计证据。此操作仍不会启用交易或提交交易所订单。
              </p>
            </div>
            <div className={latestPhase4OrderWindowAuditLog ? "phase4-status ready" : "phase4-status blocked"}>
              <span>{canRecordPhase4OrderWindow ? "可记录" : "窗口已锁定"}</span>
              <strong>{latestPhase4OrderWindowAuditLog ? "窗口已记录" : "无窗口审计"}</strong>
            </div>
          </div>
          <div className="trade-phase4-window-summary">
            <article>
              <span>交易对</span>
              <strong>{normalizedPreviewSymbol}</strong>
            </article>
            <article>
              <span>方向</span>
              <strong className={orderSide === "BUY" ? "preview-buy" : "preview-sell"}>
                {orderSideLabels[orderSide]}
              </strong>
            </article>
            <article>
              <span>限价价格</span>
              <strong>{orderForm.orderType === "LIMIT" ? `${formatNumber(parsedPrice)} USDT` : "需要限价单"}</strong>
            </article>
            <article>
              <span>数量</span>
              <strong>{Number.isFinite(parsedQuantity) ? parsedQuantity : "-"}</strong>
            </article>
            <article>
              <span>最大名义金额</span>
              <strong>{formatNumber(estimatedNotional)} USDT</strong>
            </article>
          </div>
          <div className="trade-phase4-grid">
            <label>
              <span>窗口时长</span>
              <input
                inputMode="numeric"
                value={phase4OrderWindowDuration}
                onChange={(event) => setPhase4OrderWindowDuration(event.target.value)}
                placeholder="1-10 分钟"
              />
            </label>
            <label>
              <span>当前登录密码</span>
              <input
                type="password"
                value={phase4OrderWindowPassword}
                onChange={(event) => setPhase4OrderWindowPassword(event.target.value)}
                placeholder="用于重新认证"
              />
            </label>
            <button
              className="trade-secondary-button"
              onClick={focusPhase4OrderWindowAudits}
              disabled={!activeAccount || !canViewAuditLogs || auditBusy}
            >
              加载窗口审计
            </button>
            <button
              className="trade-submit compact"
              onClick={recordPhase4OrderWindowApproval}
              disabled={!canRecordPhase4OrderWindow || apiBusy}
            >
              记录窗口审计
            </button>
          </div>
          <div className="trade-phase4-actions">
            <span>
              必需确认码：<strong>{phase4SmallFundOrderWindowAck}</strong>
            </span>
            <span>仅限限价 / 复核上限 {formatNumber(phase4MaxNotionalValue)} USDT / 不提交真实订单</span>
          </div>
        </section>

        <section className="trade-phase4-card" id="phase4-final-release-check" data-workspace="small-fund">
          <div className="trade-phase4-head">
            <div>
              <span>第四阶段最终闸门</span>
              <strong>最终确认审计</strong>
              <p>
                在复核与订单窗口审计存在后，记录小额资金测试前最终确认。此操作仅写审计，仍不授权或提交订单。
              </p>
            </div>
            <div className={latestPhase4FinalReleaseAuditLog ? "phase4-status ready" : "phase4-status blocked"}>
              <span>{canRecordPhase4FinalReleaseCheck ? "可记录" : "终审已锁定"}</span>
              <strong>
                {latestPhase4FinalReleaseAuditLog ? "终审已记录" : "无终审记录"}
              </strong>
            </div>
          </div>
          <div className="trade-phase4-window-summary">
            <article>
              <span>复核审计</span>
              <strong>{latestPhase4ReviewAuditLog ? "已记录" : "缺失"}</strong>
            </article>
            <article>
              <span>窗口审计</span>
              <strong>{latestPhase4OrderWindowAuditLog ? "已记录" : "缺失"}</strong>
            </article>
            <article>
              <span>最终名义金额</span>
              <strong>{formatNumber(estimatedNotional)} USDT</strong>
            </article>
            <article>
              <span>交易开关</span>
              <strong>{activeAccount?.trading_enabled ? "开启" : "关闭"}</strong>
            </article>
            <article>
              <span>订单授权</span>
              <strong>仅审计</strong>
            </article>
          </div>
          <div className="trade-final-confirmations">
            {[
              ["dedicatedAccount", "已确认使用专用测试账户"],
              ["accountEmpty", "账户为空或仅有已批准的小额测试资金"],
              ["withdrawalsDisabled", "交易所 API Key 已关闭提现权限"],
              ["deleteApiKeyAfterTest", "测试结束后会删除 API Key"],
              ["firstOrderStopReview", "首笔被接受订单后立即暂停并人工复核"],
              ["noLiveOrderSubmission", "此按钮仅记录审计，不会提交订单"],
            ].map(([key, label]) => (
              <label key={key}>
                <input
                  type="checkbox"
                  checked={
                    phase4FinalConfirmations[key as keyof typeof phase4FinalConfirmations]
                  }
                  onChange={(event) =>
                    setPhase4FinalConfirmations((current) => ({
                      ...current,
                      [key]: event.target.checked,
                    }))
                  }
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
          <div className="trade-phase4-grid">
            <label>
              <span>当前登录密码</span>
              <input
                type="password"
                value={phase4FinalPassword}
                onChange={(event) => setPhase4FinalPassword(event.target.value)}
                placeholder="用于重新认证"
              />
            </label>
            <button
              className="trade-secondary-button"
              onClick={focusPhase4FinalReleaseAudits}
              disabled={!activeAccount || !canViewAuditLogs || auditBusy}
            >
              加载最终审计
            </button>
            <button
              className="trade-submit compact"
              onClick={recordPhase4FinalReleaseCheck}
              disabled={!canRecordPhase4FinalReleaseCheck || apiBusy}
            >
              记录最终确认
            </button>
          </div>
          <div className="trade-phase4-actions">
            <span>
              必需确认码：<strong>{phase4FinalReleaseCheckAck}</strong>
            </span>
            <span>需要复核审计 + 订单窗口审计 / 不提交真实订单</span>
          </div>
        </section>

        <section className="trade-api-grid" data-workspace="portfolio">
          {exchanges.map((exchange) => {
            const count = accounts.filter((account) => account.exchange_name === exchange).length;
            return (
              <article className="trade-card" key={exchange}>
                <span>{exchange.toUpperCase()}</span>
                <strong>{count}</strong>
                <p>{count === 0 ? "暂无 API 账户" : "已有只读或测试账户"}</p>
              </article>
            );
          })}
        </section>

        <section className="trade-bottom-grid" data-workspace="terminal-audit">
          <div className="trade-card">
            <div className="trade-tabs">
              <button
                className={bottomTab === "balances" ? "active" : ""}
                onClick={() => setBottomTab("balances")}
              >
                资产
              </button>
              <button
                className={bottomTab === "orders" ? "active" : ""}
                onClick={() => setBottomTab("orders")}
              >
                当前委托
              </button>
              <button
                className={bottomTab === "history" ? "active" : ""}
                onClick={() => setBottomTab("history")}
              >
                历史记录
              </button>
              <button
                className={bottomTab === "audit" ? "active" : ""}
                onClick={() => setBottomTab("audit")}
              >
                审计
              </button>
            </div>
            {bottomTab === "balances" && (
              <div className="trade-audit-panel">
                <div className="trade-audit-heading">
                  <div>
                    <strong>账户资产</strong>
                    <span>只读读取所选 OKX 正式账户余额，按原始币种展示，不进行估值换算。</span>
                  </div>
                  <button
                    className="trade-secondary-button"
                    onClick={loadBalances}
                    disabled={!canLoadBalances || balancesLoading}
                  >
                    {balancesLoading ? "读取中" : "刷新资产"}
                  </button>
                </div>
                {!canLoadBalances && (
                  <div className="trade-empty-table">
                    请选择已配置密钥、交易标记关闭的 OKX 正式只读账户后再读取资产。
                  </div>
                )}
                {canLoadBalances && balances.length === 0 && !balancesLoading && (
                  <div className="trade-empty-table">
                    {balancesLoadedAt ? "账户当前没有返回资产余额。" : "尚未读取账户资产。"}
                  </div>
                )}
                {balances.length > 0 && (
                  <div className="trade-balances-table">
                    <div className="trade-balances-row trade-balances-header">
                      <span>币种</span>
                      <span>可用</span>
                      <span>冻结</span>
                      <span>总额</span>
                    </div>
                    {balances.map((balance) => (
                      <div className="trade-balances-row" key={balance.asset}>
                        <strong className="trade-balance-asset">{balance.asset}</strong>
                        <span>{balance.free ?? "-"}</span>
                        <span>{balance.locked ?? "-"}</span>
                        <span>{balance.total ?? "-"}</span>
                      </div>
                    ))}
                  </div>
                )}
                {balancesLoadedAt && (
                  <span className="trade-open-orders-time">
                    最后读取：{balancesLoadedAt} · {balances.length} 个币种
                  </span>
                )}
              </div>
            )}
            {bottomTab === "orders" && (
              <div className="trade-audit-panel">
                <div className="trade-audit-heading">
                  <div>
                    <strong>当前委托</strong>
                    <span>仅手动刷新读取 OKX 正式账户当前未完成委托，不提供平台撤单或下单。</span>
                  </div>
                  <button
                    className="trade-secondary-button"
                    onClick={loadOpenOrders}
                    disabled={!canLoadOpenOrders || openOrdersLoading}
                  >
                    {openOrdersLoading ? "读取中" : "刷新当前委托"}
                  </button>
                </div>
                {!canLoadOpenOrders && (
                  <div className="trade-empty-table">
                    请选择已配置密钥、交易标记关闭的 OKX 正式只读账户后再读取当前委托。
                  </div>
                )}
                {canLoadOpenOrders && openOrders.length === 0 && !openOrdersLoading && (
                  <div className="trade-empty-table">
                    {openOrdersLoadedAt ? "当前没有未完成委托。" : "尚未读取当前委托。"}
                  </div>
                )}
                {openOrders.length > 0 && (
                  <div className="trade-open-orders-table">
                    <div className="trade-open-orders-row trade-open-orders-header">
                      <span>交易对</span>
                      <span>方向</span>
                      <span>类型</span>
                      <span>价格</span>
                      <span>数量 / 已成交</span>
                      <span>状态</span>
                    </div>
                    {openOrders.map((order, index) => (
                      <div className="trade-open-orders-row" key={order.order_id ?? `${order.symbol}-${index}`}>
                        <span>{order.symbol ?? "-"}</span>
                        <span className={order.side?.toLowerCase() === "buy" ? "preview-buy" : "preview-sell"}>
                          {order.side?.toUpperCase() === "BUY" ? "买入" : order.side?.toUpperCase() === "SELL" ? "卖出" : "-"}
                        </span>
                        <span>{order.order_type ?? "-"}</span>
                        <span>{order.price ?? "-"}</span>
                        <span>{order.quantity ?? "-"} / {order.filled_quantity ?? "-"}</span>
                        <span>{order.status ?? "-"}</span>
                      </div>
                    ))}
                  </div>
                )}
                {openOrdersLoadedAt && <span className="trade-open-orders-time">最后读取：{openOrdersLoadedAt}</span>}
              </div>
            )}
            {bottomTab === "history" && (
              <div className="trade-empty-table">
                执行历史会展示已接受的 Mock 订单和交易所只读探测结果。
              </div>
            )}
            {bottomTab === "audit" && (
              <div className="trade-audit-panel">
                <div className="trade-audit-heading">
                  <div>
                    <strong>审计日志</strong>
                    <span>仅追加记录，管理员只读查询</span>
                  </div>
                  <span>已加载 {auditLogs.length} 条{auditLoadedAt ? ` · ${auditLoadedAt}` : ""}</span>
                </div>
                {canViewAuditLogs ? (
                  <>
                    <div className="trade-audit-presets">
                      <button
                        className="trade-secondary-button"
                        onClick={() => setAuditFilterPreset("currentUser")}
                        disabled={!session.userId}
                      >
                        当前用户
                      </button>
                      <button
                        className="trade-secondary-button"
                        onClick={() => setAuditFilterPreset("currentAccount")}
                        disabled={!activeAccountId}
                      >
                        当前账户
                      </button>
                      <button
                        className="trade-secondary-button"
                        onClick={() => setAuditFilterPreset("errors")}
                      >
                        仅错误
                      </button>
                      <button
                        className="trade-secondary-button"
                        onClick={focusAuditForCurrentAccount}
                        disabled={!activeAccountId}
                      >
                        当前账户只读
                      </button>
                      <button
                        className="trade-secondary-button"
                        onClick={focusTestnetApprovalAudits}
                        disabled={!activeAccountId}
                      >
                        测试网窗口
                      </button>
                      <button
                        className="trade-secondary-button"
                        onClick={() => setAuditFilterPreset("clear")}
                      >
                        清空筛选
                      </button>
                    </div>
                    <div className="trade-audit-filters">
                      <label>
                        用户 ID
                        <input
                          value={auditFilters.userId}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              userId: event.target.value,
                            }))
                          }
                          placeholder="可选"
                        />
                      </label>
                      <label>
                        账户 ID
                        <input
                          value={auditFilters.exchangeAccountId}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              exchangeAccountId: event.target.value,
                            }))
                          }
                          placeholder="可选"
                        />
                      </label>
                      <label>
                        动作
                        <select
                          value={auditFilters.action}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              action: event.target.value,
                            }))
                          }
                        >
                          <option value="">全部</option>
                          {auditActionOptions.map((action) => (
                            <option key={action} value={action}>
                              {action}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        级别
                        <select
                          value={auditFilters.severity}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              severity: event.target.value,
                            }))
                          }
                        >
                          <option value="">全部</option>
                          <option value="INFO">信息</option>
                          <option value="OK">正常</option>
                          <option value="WARNING">警告</option>
                          <option value="ERROR">错误</option>
                        </select>
                      </label>
                      <label>
                        开始时间
                        <input
                          type="datetime-local"
                          value={auditFilters.createdFrom}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              createdFrom: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <label>
                        结束时间
                        <input
                          type="datetime-local"
                          value={auditFilters.createdTo}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              createdTo: event.target.value,
                            }))
                          }
                        />
                      </label>
                      <label>
                        条数
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
                        {auditBusy ? "加载中" : "加载"}
                      </button>
                      <button
                        className="trade-secondary-button"
                        onClick={exportAuditReport}
                        disabled={!auditLogs.length}
                      >
                        导出 JSON
                      </button>
                    </div>
                    <div className="trade-audit-summary">
                      {["INFO", "OK", "WARNING", "ERROR"].map((severity) => (
                        <span key={severity}>
                          {severityLabels[severity] ?? severity} <strong>{auditSeverityCounts[severity] ?? 0}</strong>
                        </span>
                      ))}
                      <span>
                        测试网窗口 <strong>{approvalAuditLogs.length}</strong>
                      </span>
                      <span>
                        第四阶段复核 <strong>{phase4ReviewAuditLogs.length}</strong>
                      </span>
                      <span>
                        真实窗口 <strong>{phase4OrderWindowAuditLogs.length}</strong>
                      </span>
                      <span>
                        最终确认 <strong>{phase4FinalReleaseAuditLogs.length}</strong>
                      </span>
                    </div>
                    {latestApprovalAuditLog ? (
                      <article className="trade-audit-highlight">
                        <div>
                        <span>最新测试网审批窗口</span>
                          <strong>{formatDateTime(latestApprovalAuditLog.created_at)}</strong>
                        </div>
                        <dl>
                          <div>
                            <dt>交易对</dt>
                            <dd>{String(latestApprovalAuditLog.payload.symbol ?? "-")}</dd>
                          </div>
                          <div>
                            <dt>方向</dt>
                            <dd>{String(latestApprovalAuditLog.payload.side ?? "-")}</dd>
                          </div>
                          <div>
                            <dt>订单授权</dt>
                            <dd>
                              {latestApprovalAuditLog.payload.order_submission_authorized === true
                                ? "已授权"
                                : "仅审计"}
                            </dd>
                          </div>
                          <div>
                            <dt>过期时间</dt>
                            <dd>
                              {latestApprovalAuditLog.payload.expires_at
                                ? formatDateTime(String(latestApprovalAuditLog.payload.expires_at))
                                : "-"}
                            </dd>
                          </div>
                        </dl>
                      </article>
                    ) : null}
                    {auditLogs.length === 0 ? (
                      <div className="trade-empty-table">
                        暂未加载审计记录。请选择筛选条件并点击加载。
                      </div>
                    ) : (
                      <div className="trade-audit-workspace">
                        <div className="trade-audit-table" role="table" aria-label="审计日志记录">
                          <div className="trade-audit-table-head" role="row">
                            <span>时间</span>
                            <span>级别</span>
                            <span>动作</span>
                            <span>用户</span>
                            <span>账户</span>
                          </div>
                          {auditLogs.map((record) => (
                            <button
                              className={record.id === selectedAuditLogId ? "selected" : ""}
                              key={record.id}
                              onClick={() => setSelectedAuditLogId(record.id)}
                              role="row"
                            >
                              <span>{formatDateTime(record.created_at)}</span>
                              <em>{severityLabels[record.severity] ?? record.severity}</em>
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
                                  <span>选中记录</span>
                                  <strong>{selectedAuditLog.action}</strong>
                                </div>
                                <em>{severityLabels[selectedAuditLog.severity] ?? selectedAuditLog.severity}</em>
                              </header>
                              <dl>
                                <div>
                                  <dt>创建时间</dt>
                                  <dd>{formatDateTime(selectedAuditLog.created_at)}</dd>
                                </div>
                                <div>
                                  <dt>用户</dt>
                                  <dd>{selectedAuditLog.user_id}</dd>
                                </div>
                                <div>
                                  <dt>账户</dt>
                                  <dd>{selectedAuditLog.exchange_account_id ?? "-"}</dd>
                                </div>
                                <div>
                                  <dt>ID</dt>
                                  <dd>{selectedAuditLog.id}</dd>
                                </div>
                              </dl>
                              {selectedApprovalPayload ? (
                                <div className="trade-approval-grid">
                                  <div>
                                    <span>交易对</span>
                                    <strong>{String(selectedApprovalPayload.symbol ?? "-")}</strong>
                                  </div>
                                  <div>
                                    <span>方向</span>
                                    <strong>{String(selectedApprovalPayload.side ?? "-")}</strong>
                                  </div>
                                  <div>
                                    <span>最大数量</span>
                                    <strong>{String(selectedApprovalPayload.max_quantity ?? "-")}</strong>
                                  </div>
                                  <div>
                                    <span>最大名义金额</span>
                                    <strong>{String(selectedApprovalPayload.max_notional ?? "-")}</strong>
                                  </div>
                                  <div>
                                    <span>提交状态</span>
                                    <strong>
                                      {selectedApprovalPayload.order_submission_authorized === true
                                        ? "已授权"
                                        : "仅审计"}
                                    </strong>
                                  </div>
                                  <div>
                                    <span>交易标志</span>
                                    <strong>
                                      {selectedApprovalPayload.trading_flags_changed === true
                                        ? "已变更"
                                        : "未变更"}
                                    </strong>
                                  </div>
                                </div>
                              ) : null}
                              <pre>{prettyJson(selectedAuditLog.payload)}</pre>
                            </>
                          ) : (
                            <div className="trade-empty-table">请选择一条审计记录。</div>
                          )}
                        </article>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="trade-empty-table">
                    审计视图仅管理员可见。请使用 admin 或 super_admin 账户查询记录。
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="trade-card">
            <div className="trade-card-head">
              <strong>风控快照</strong>
              <span>统一风控</span>
            </div>
            <dl className="trade-risk-list">
              <div>
                <dt>交易</dt>
                <dd>默认关闭</dd>
              </div>
              <div>
                <dt>真实账户</dt>
                <dd>只读</dd>
              </div>
              <div>
                <dt>最新结果</dt>
                <dd>{resultLabels[lastStatus] ?? lastStatus}</dd>
              </div>
            </dl>
          </div>
        </section>
      </section>
      {isOrderPreviewOpen && (
        <div className="trade-modal-backdrop" role="presentation">
          <section
            aria-labelledby="order-preview-title"
            aria-modal="true"
            className="trade-preview-modal"
            role="dialog"
          >
            <header>
              <div>
                <span>订单预览</span>
                <h2 id="order-preview-title">
                  {activeSymbol} {orderSideLabels[orderSide]}
                </h2>
              </div>
              <button
                aria-label="关闭订单预览"
                className="trade-icon-button"
                onClick={() => setIsOrderPreviewOpen(false)}
              >
                X
              </button>
            </header>
            <div className="trade-preview-warning">
               <strong>{canRecordTestnetOrderWindow ? "测试网审批窗口" : orderLocked ? "已锁定" : "仅预览"}</strong>
               <span>
                 {selectedAccountRoute} 此页面不会提交交易所订单。测试网审批仅在密码重新认证后记录审计窗口。
               </span>
            </div>
            <dl className="trade-preview-grid">
              <div>
                 <dt>交易所</dt>
                <dd>{activeExchangeProfile.label}</dd>
              </div>
              <div>
                 <dt>账户</dt>
                <dd>{activeAccount?.account_label ?? "-"}</dd>
              </div>
              <div>
                 <dt>模式</dt>
                 <dd>{safeAccountModeLabel(activeAccount?.account_mode)}</dd>
              </div>
              <div>
                 <dt>账户状态</dt>
                <dd>{activeAccountHealth}</dd>
              </div>
              <div>
                 <dt>订单类型</dt>
                 <dd>{orderTypeLabels[orderForm.orderType]}</dd>
              </div>
              <div>
                 <dt>方向</dt>
                 <dd className={orderSide === "BUY" ? "preview-buy" : "preview-sell"}>
                   {orderSideLabels[orderSide]}
                 </dd>
              </div>
              <div>
                 <dt>参考价格</dt>
                <dd>{formatNumber(referencePrice)} USDT</dd>
              </div>
              <div>
                 <dt>数量</dt>
                <dd>{Number.isFinite(parsedQuantity) ? parsedQuantity : "-"}</dd>
              </div>
              <div>
                 <dt>预估名义金额</dt>
                <dd>{formatNumber(estimatedNotional)} USDT</dd>
              </div>
            </dl>
            <div className="trade-route-panel">
               <span>客户端订单 ID 预览</span>
              <code>{clientOrderIdPreview}</code>
            </div>
            {lockReasons.length > 0 && (
              <ul className="trade-lock-list">
                {lockReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
            {activeAccount?.account_mode === "TESTNET" && activeExchange !== "mock" && (
              <div className="trade-route-panel">
                 <span>测试网订单窗口</span>
                 <strong>仅审计 / 5 分钟 / 不改变交易标志</strong>
                {testnetWindowReasons.length > 0 ? (
                  <ul className="trade-lock-list compact">
                    {testnetWindowReasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                ) : (
                  <label className="trade-field">
                     当前登录密码
                    <input
                      type="password"
                      value={orderApprovalPassword}
                      onChange={(event) => setOrderApprovalPassword(event.target.value)}
                       placeholder="用于审批审计"
                    />
                  </label>
                )}
              </div>
            )}
            <pre className="trade-preview-json">{prettyJson(orderPreviewPayload)}</pre>
            <footer>
              <button className="trade-secondary-button" onClick={focusAuditForCurrentAccount}>
                 相关审计
              </button>
              <button className="trade-secondary-button" onClick={() => setIsOrderPreviewOpen(false)}>
                 取消
              </button>
              {activeAccount?.account_mode === "TESTNET" && activeExchange !== "mock" && (
                <button
                  className="trade-secondary-button"
                  disabled={!canRecordTestnetOrderWindow || apiBusy}
                  onClick={recordTestnetOrderWindowApproval}
                >
                   记录测试网窗口
                </button>
              )}
              <button className="trade-submit compact" disabled={orderLocked} onClick={confirmOrderPreview}>
                 确认预览
              </button>
            </footer>
          </section>
        </div>
      )}
    </main>
  );
}
