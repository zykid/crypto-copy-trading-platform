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

type BottomTab = "positions" | "orders" | "history" | "audit";
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
  const [bottomTab, setBottomTab] = useState<BottomTab>("positions");
  const [auditBusy, setAuditBusy] = useState(false);