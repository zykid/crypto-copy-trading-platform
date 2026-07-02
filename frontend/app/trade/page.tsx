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

const apiBaseFallback = "http://192.168.2.42:8000/api/v1";
const exchanges: ExchangeName[] = ["okx", "binance", "bybit", "mock"];
const symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"];
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
    venue: "Unified Account",
    route: "REAL / TESTNET read-only",
    window: "Balances, positions, and order checks stay read-only.",
  },
  binance: {
    label: "Binance",
    venue: "Spot / Futures",
    route: "TESTNET read-only",
    window: "Adapter window is reserved for testnet validation.",
  },
  bybit: {
    label: "Bybit",
    venue: "Unified Trading",
    route: "TESTNET read-only",
    window: "Adapter window is reserved for testnet validation.",
  },
  mock: {
    label: "Mock Exchange",
    venue: "Simulation",
    route: "Simulation executable",
    window: "Mock route can execute only after account trading and risk checks pass.",
  },
};
const marketSnapshots: Record<string, { last: number; bid: number; ask: number; change: string }> = {
  "BTC/USDT": { last: 68420.5, bid: 68410, ask: 68428.2, change: "+1.42%" },
  "ETH/USDT": { last: 3582.16, bid: 3581.4, ask: 3583.2, change: "+0.86%" },
  "SOL/USDT": { last: 151.72, bid: 151.61, ask: 151.84, change: "-0.31%" },
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

function toAuditQueryDateTime(value: string) {
  if (!value.trim()) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    throw new Error(`Invalid audit date filter: ${value}`);
  }
  return date.toISOString();
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

function formatNumber(value: number, maximumFractionDigits = 2) {
  if (!Number.isFinite(value)) {
    return "-";
  }
  return new Intl.NumberFormat("en-US", { maximumFractionDigits }).format(value);
}

export default function TradeWorkspace() {
  const [apiRoot] = useState(resolveApiBase);
  const [session, setSession] = useState<SessionState>(emptySession);
  const [accounts, setAccounts] = useState<ExchangeAccount[]>([]);
  const [activeExchange, setActiveExchange] = useState<ExchangeName>("okx");
  const [activeSymbol, setActiveSymbol] = useState("BTC/USDT");
  const [activeAccountId, setActiveAccountId] = useState("");
  const [orderSide, setOrderSide] = useState<OrderSide>("BUY");
  const [orderForm, setOrderForm] = useState({
    orderType: "MARKET" as OrderType,
    price: "",
    quantity: "0.001",
  });
  const [lastStatus, setLastStatus] = useState("READ ONLY");
  const [apiKeyMetadata, setApiKeyMetadata] = useState<ApiKeyMetadata>(emptyMetadata);
  const [apiBusy, setApiBusy] = useState(false);
  const [apiLogs, setApiLogs] = useState<ApiActionLog[]>([]);
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

  useEffect(() => {
    setPhase4Readiness(null);
    setPhase4ReviewPassword("");
    setPhase4OrderWindowPassword("");
    setPhase4FinalPassword("");
  }, [activeAccountId]);

  useEffect(() => {
    function syncHashToPanel() {
      if (window.location.hash === "#audit") {
        setBottomTab("audit");
      }
    }

    syncHashToPanel();
    window.addEventListener("hashchange", syncHashToPanel);
    return () => window.removeEventListener("hashchange", syncHashToPanel);
  }, []);

  const activeAccount = allSelectedAccount;
  const accountMode = activeAccount?.account_mode ?? "UNSELECTED";
  const activeExchangeProfile = exchangeProfiles[activeExchange];
  const activeAccountHealth = !activeAccount
    ? "NO ACCOUNT"
    : activeAccount.is_active
      ? activeAccount.trading_enabled
        ? "TRADING ENABLED"
        : "READ ONLY"
      : "INACTIVE";
  const selectedAccountRoute = activeAccount
    ? `${activeExchangeProfile.label} / ${activeAccount.account_mode} / ${
        activeAccount.trading_enabled ? "trading flag on" : "read-only flag"
      }`
    : "Select an exchange account to bind this ticket.";
  const activeMarket = marketSnapshots[activeSymbol] ?? marketSnapshots["BTC/USDT"];
  const parsedPrice = Number(orderForm.price);
  const parsedQuantity = Number(orderForm.quantity);
  const referencePrice =
    orderForm.orderType === "LIMIT" && Number.isFinite(parsedPrice) && parsedPrice > 0
      ? parsedPrice
      : activeMarket.last;
  const estimatedNotional =
    Number.isFinite(parsedQuantity) && parsedQuantity > 0 ? parsedQuantity * referencePrice : 0;
  const normalizedPreviewSymbol = activeSymbol.replace("/", "");
  const clientOrderIdPreview = activeAccount
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
    secret_configured: apiKeyMetadata.configured,
    trading_enabled: activeAccount?.trading_enabled ?? false,
  };
  const lockReasons = [
    !session.token ? "Login required" : null,
    !activeAccount ? "Select an exchange account" : null,
    activeAccount && !activeAccount.is_active ? "Account is inactive" : null,
    activeAccount?.account_mode === "REAL" ? "REAL account is read-only in this stage" : null,
    activeExchange !== "mock" ? "Only Mock can be executable from this ticket" : null,
    activeAccount && !activeAccount.trading_enabled ? "Account trading flag is disabled" : null,
    !Number.isFinite(parsedQuantity) || parsedQuantity <= 0 ? "Quantity must be greater than 0" : null,
    orderForm.orderType === "LIMIT" && (!Number.isFinite(parsedPrice) || parsedPrice <= 0)
      ? "Limit price is required"
      : null,
  ].filter(Boolean) as string[];
  const testnetWindowReasons = [
    !session.token ? "Login required" : null,
    !activeAccount ? "Select an exchange account" : null,
    activeAccount && !activeAccount.is_active ? "Account is inactive" : null,
    activeAccount?.account_mode !== "TESTNET" ? "Account mode must be TESTNET" : null,
    activeExchange === "mock" ? "Mock uses simulation flow instead of a testnet window" : null,
    activeAccount?.trading_enabled ? "Account trading flag must stay disabled before approval" : null,
    !apiKeyMetadata.configured ? "Encrypted API key metadata is required" : null,
    !Number.isFinite(parsedQuantity) || parsedQuantity <= 0 ? "Quantity must be greater than 0" : null,
    estimatedNotional <= 0 ? "Estimated notional must be greater than 0" : null,
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
      title: "Authenticated session",
      detail: session.token ? `${session.username} / ${session.role}` : "Login is required before account checks.",
      required: true,
      status: session.token ? "pass" : "pending",
    },
    {
      id: "mock",
      title: "Mock execution path",
      detail:
        mockAccounts.length > 0
          ? `${mockAccounts.length} simulation account available.`
          : "Create and run the Mock chain before exchange checks.",
      required: true,
      status: mockAccounts.length > 0 ? "pass" : "pending",
    },
    {
      id: "exchange-account",
      title: "Read-only exchange account",
      detail:
        exchangeReadOnlyAccounts.length > 0
          ? `${exchangeReadOnlyAccounts.length} TESTNET/REAL read-only account available.`
          : "Add a TESTNET or REAL account with trading disabled.",
      required: true,
      status: exchangeReadOnlyAccounts.length > 0 ? "pass" : "pending",
    },
    {
      id: "active-account",
      title: "Active account selected",
      detail: activeAccount
        ? `${defaultAccountLabel(activeAccount.exchange_name, activeAccount.account_mode)} selected.`
        : "Select an account in API Management.",
      required: true,
      status: activeAccount ? "pass" : "pending",
    },
    {
      id: "trading-flag",
      title: "Trading flag remains disabled",
      detail: activeAccount
        ? activeAccount.trading_enabled
          ? "Active account can trade; keep this disabled before small-fund testing."
          : "Active account is read-only from the platform side."
        : "Select an account to inspect the trading flag.",
      required: true,
      status: activeAccount ? (activeAccount.trading_enabled ? "fail" : "pass") : "pending",
    },
    {
      id: "secret",
      title: "Encrypted secret metadata",
      detail: apiKeyMetadata.configured
        ? "Secret is configured and not returned to the browser."
        : "Save the API key and secret for the selected account.",
      required: true,
      status: apiKeyMetadata.configured ? "pass" : "pending",
    },
    {
      id: "read-only-auth",
      title: "Read-only authentication evidence",
      detail: activeReadOnlyAuthenticationAudit
        ? `${activeReadOnlyAuthenticationAudit.action} recorded in audit logs.`
        : "Run read-only authentication and load the active account audit logs.",
      required: true,
      status: activeReadOnlyAuthenticationAudit ? "pass" : "pending",
    },
    {
      id: "audit-errors",
      title: "No current audit errors",
      detail: auditHasErrors
        ? `${auditSeverityCounts.ERROR} error audit record(s) in the loaded view.`
        : "Loaded audit view has no ERROR records.",
      required: true,
      status: auditHasErrors ? "fail" : "pass",
    },
    {
      id: "live-boundary",
      title: "Live order boundary",
      detail: liveOrderBoundaryIsLocked
        ? "REAL order submission remains locked in this UI."
        : "REAL trading is enabled on the active account.",
      required: true,
      status: liveOrderBoundaryIsLocked ? "pass" : "fail",
    },
    {
      id: "testnet-window",
      title: "TESTNET order window audit",
      detail:
        approvalAuditLogs.length > 0
          ? `${approvalAuditLogs.length} approval window audit record(s) loaded.`
          : "Optional: record a TESTNET order-window approval before testnet order drills.",
      required: false,
      status: approvalAuditLogs.length > 0 ? "pass" : "warn",
    },
    {
      id: "phase4-review",
      title: "Phase 4 small-fund review",
      detail: latestPhase4ReviewAuditLog
        ? "REAL small-fund review audit is recorded without authorizing orders."
        : "Optional before small funds: record a super-admin review after REAL read-only readiness passes.",
      required: false,
      status: latestPhase4ReviewAuditLog ? "pass" : "warn",
    },
    {
      id: "phase4-real-window",
      title: "REAL small-fund order window",
      detail: latestPhase4OrderWindowAuditLog
        ? "REAL small-fund order window approval is recorded as audit-only evidence."
        : "Optional final gate: record exact symbol, side, quantity, price, notional, and duration.",
      required: false,
      status: latestPhase4OrderWindowAuditLog ? "pass" : "warn",
    },
    {
      id: "phase4-final-release",
      title: "Phase 4 final release check",
      detail: latestPhase4FinalReleaseAuditLog
        ? "Final release-check audit is recorded; platform order submission is still not authorized."
        : "Optional: record final pre-small-fund confirmations after review and order-window audits exist.",
      required: false,
      status: latestPhase4FinalReleaseAuditLog ? "pass" : "warn",
    },
  ];
  const requiredPreRealItems = preRealChecklist.filter((item) => item.required);
  const completedRequiredPreRealItems = requiredPreRealItems.filter((item) => item.status === "pass").length;
  const preRealReady = completedRequiredPreRealItems === requiredPreRealItems.length;
  const nextPreRealAction =
    preRealChecklist.find((item) => item.required && item.status !== "pass")?.detail ??
    "All required checks are complete. Next step is a manual small-fund review, not live automation.";
  const orderLocked = lockReasons.length > 0;
  const canRecordTestnetOrderWindow = testnetWindowReasons.length === 0;

  const marketRows = [
    { price: formatNumber(activeMarket.ask), amount: "0.184", side: "ask" },
    { price: formatNumber(activeMarket.ask - activeMarket.last * 0.0001), amount: "0.076", side: "ask" },
    { price: formatNumber(activeMarket.bid), amount: "0.214", side: "bid" },
    { price: formatNumber(activeMarket.bid - activeMarket.last * 0.00008), amount: "0.092", side: "bid" },
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
      appendApiLog("Load audit logs", false, "Admin role required");
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
      appendApiLog("Load audit logs", true, {
        count: records.length,
        action: filterOverride.action || "*",
        severity: filterOverride.severity || "*",
        created_from: createdFrom || "*",
        created_to: createdTo || "*",
      });
    } catch (error) {
      appendApiLog("Load audit logs", false, String(error));
    } finally {
      setAuditBusy(false);
    }
  }

  function exportAuditReport() {
    if (!auditLogs.length) {
      appendApiLog("Export audit report", false, "Load audit logs first");
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
    appendApiLog("Export audit report", true, {
      record_count: auditLogs.length,
      generated_at: generatedAt,
    });
  }

  function openOrderPreview() {
    setIsOrderPreviewOpen(true);
    setLastStatus(orderLocked ? "PREVIEW LOCKED" : "PREVIEW READY");
  }

  function selectAccountForTrading(account: ExchangeAccount) {
    setActiveExchange(account.exchange_name);
    setActiveAccountId(account.id);
    setBottomTab("positions");
    setLastStatus("ACCOUNT SELECTED");
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
    setLastStatus("AUDIT FILTER READY");
    if (canViewAuditLogs && session.token) {
      void loadAuditLogs(nextFilters);
    }
  }

  function focusTestnetApprovalAudits() {
    if (!activeAccount) {
      appendApiLog("Focus testnet approval audit", false, "Select an account first");
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
    setLastStatus("APPROVAL AUDIT FILTER READY");
    if (canViewAuditLogs && session.token) {
      void loadAuditLogs(nextFilters);
    }
  }

  function focusPhase4ReviewAudits() {
    if (!activeAccount) {
      appendApiLog("Focus Phase 4 review audit", false, "Select an account first");
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
    setLastStatus("PHASE 4 REVIEW AUDIT FILTER READY");
    if (canViewAuditLogs && session.token) {
      void loadAuditLogs(nextFilters);
    }
  }

  function focusPhase4OrderWindowAudits() {
    if (!activeAccount) {
      appendApiLog("Focus Phase 4 REAL order window audit", false, "Select an account first");
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
    setLastStatus("PHASE 4 ORDER WINDOW AUDIT FILTER READY");
    if (canViewAuditLogs && session.token) {
      void loadAuditLogs(nextFilters);
    }
  }

  function focusPhase4FinalReleaseAudits() {
    if (!activeAccount) {
      appendApiLog("Focus Phase 4 final release audit", false, "Select an account first");
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
    setLastStatus("PHASE 4 FINAL AUDIT FILTER READY");
    if (canViewAuditLogs && session.token) {
      void loadAuditLogs(nextFilters);
    }
  }

  async function loadPhase4Readiness() {
    if (!activeAccount) {
      appendApiLog("Load Phase 4 readiness", false, "Select a REAL OKX account first");
      return;
    }
    setApiBusy(true);
    try {
      const report = (await apiRequest(
        "GET",
        `/exchange-accounts/${activeAccount.id}/phase4-readiness`,
      )) as Phase4ReadinessReport;
      setPhase4Readiness(report);
      appendApiLog("Load Phase 4 readiness", report.overall_status === "PASS", report);
    } catch (error) {
      setPhase4Readiness(null);
      appendApiLog("Load Phase 4 readiness", false, String(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function recordPhase4SmallFundReview() {
    if (!activeAccount) {
      appendApiLog("Record Phase 4 review", false, "Select a REAL OKX account first");
      return;
    }
    if (!phase4ReviewPassword) {
      appendApiLog("Record Phase 4 review", false, "Current password is required");
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
      appendApiLog("Record Phase 4 review", true, result);
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
      appendApiLog("Record Phase 4 review", false, String(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function recordPhase4OrderWindowApproval() {
    if (!activeAccount || !canRecordPhase4OrderWindow) {
      return;
    }
    if (!phase4OrderWindowPassword) {
      appendApiLog("Record Phase 4 REAL order window", false, "Current password is required");
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
      appendApiLog("Record Phase 4 REAL order window", true, result);
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
      appendApiLog("Record Phase 4 REAL order window", false, String(error));
    } finally {
      setApiBusy(false);
    }
  }

  async function recordPhase4FinalReleaseCheck() {
    if (!activeAccount || !canRecordPhase4FinalReleaseCheck) {
      return;
    }
    if (!phase4FinalPassword) {
      appendApiLog("Record Phase 4 final check", false, "Current password is required");
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
      appendApiLog("Record Phase 4 final check", true, result);
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
      appendApiLog("Record Phase 4 final check", false, String(error));
    } finally {
      setApiBusy(false);
    }
  }

  function confirmOrderPreview() {
    if (orderLocked) {
      return;
    }
    appendApiLog("Order preview confirmed", true, orderPreviewPayload);
    setBottomTab("history");
    setIsOrderPreviewOpen(false);
  }

  async function recordTestnetOrderWindowApproval() {
    if (!activeAccount || !canRecordTestnetOrderWindow) {
      return;
    }
    if (!orderApprovalPassword) {
      appendApiLog("Record testnet order window", false, "Current password is required");
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
      appendApiLog("Record testnet order window", true, result);
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
      appendApiLog("Record testnet order window", false, String(error));
    } finally {
      setApiBusy(false);
    }
  }

  function focusAuditForCurrentAccount() {
    if (!activeAccount) {
      appendApiLog("Focus audit logs", false, "Select an account first");
      return;
    }
    focusAuditForAccount(activeAccount);
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
          <a href="/trade#audit">Audit Logs</a>
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
                <span>{accountCount} accounts</span>
              </button>
            );
          })}
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
                  {activeExchangeProfile.label} / {activeSymbol}
                </strong>
              </div>
              <em>
                {formatNumber(activeMarket.last)} USDT {activeMarket.change}
              </em>
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
            <div className="trade-exchange-window">
              <div>
                <span>Exchange Window</span>
                <strong>{activeExchangeProfile.venue}</strong>
              </div>
              <div className="trade-window-status">
                <span>{activeExchangeProfile.label}</span>
                <strong>{activeAccountHealth}</strong>
              </div>
              <dl>
                <div>
                  <dt>Account</dt>
                  <dd>{activeAccount?.account_label ?? "Not selected"}</dd>
                </div>
                <div>
                  <dt>Mode</dt>
                  <dd>{accountMode}</dd>
                </div>
                <div>
                  <dt>Route</dt>
                  <dd>{activeExchangeProfile.route}</dd>
                </div>
                <div>
                  <dt>Secret</dt>
                  <dd>{apiKeyMetadata.configured ? "Configured" : "Not set"}</dd>
                </div>
              </dl>
              <div className="trade-window-route">
                <span>Ticket Binding</span>
                <strong>{selectedAccountRoute}</strong>
              </div>
              <p>{activeExchangeProfile.window}</p>
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
            <div className="trade-ticket-mode" aria-label="order type selector">
              <button
                className={orderForm.orderType === "MARKET" ? "active" : ""}
                onClick={() => setOrderForm((current) => ({ ...current, orderType: "MARKET" }))}
              >
                Market
              </button>
              <button
                className={orderForm.orderType === "LIMIT" ? "active" : ""}
                onClick={() => setOrderForm((current) => ({ ...current, orderType: "LIMIT" }))}
              >
                Limit
              </button>
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
              <input
                inputMode="decimal"
                readOnly={orderForm.orderType === "MARKET"}
                value={
                  orderForm.orderType === "MARKET"
                    ? `Market / ${formatNumber(activeMarket.last)}`
                    : orderForm.price
                }
                onChange={(event) =>
                  setOrderForm((current) => ({ ...current, price: event.target.value }))
                }
              />
            </label>
            <label>
              Quantity
              <input
                inputMode="decimal"
                value={orderForm.quantity}
                onChange={(event) =>
                  setOrderForm((current) => ({ ...current, quantity: event.target.value }))
                }
              />
            </label>
            <label>
              Account
              <select
                value={activeAccountId}
                onChange={(event) => setActiveAccountId(event.target.value)}
              >
                {exchangeAccounts.length === 0 ? (
                  <option value="">No {activeExchangeProfile.label} account</option>
                ) : (
                  exchangeAccounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.account_label} / {account.account_mode}
                    </option>
                  ))
                )}
              </select>
            </label>
            <div className="trade-ticket-account">
              <span>Selected Route</span>
              <strong>{selectedAccountRoute}</strong>
            </div>
            <div className="trade-order-preview">
              <div>
                <span>Side</span>
                <strong className={orderSide === "BUY" ? "preview-buy" : "preview-sell"}>
                  {orderSide}
                </strong>
              </div>
              <div>
                <span>Type</span>
                <strong>{orderForm.orderType}</strong>
              </div>
              <div>
                <span>Estimated Price</span>
                <strong>{formatNumber(referencePrice)} USDT</strong>
              </div>
              <div>
                <span>Estimated Notional</span>
                <strong>{formatNumber(estimatedNotional)} USDT</strong>
              </div>
            </div>
            <div className="trade-route-panel">
              <span>Client Order ID Preview</span>
              <code>{clientOrderIdPreview}</code>
            </div>
            <button className="trade-submit" onClick={openOrderPreview}>
              Review Order Preview
            </button>
            {lockReasons.length === 0 ? (
              <p>Mock preview route is open. This view still does not submit orders.</p>
            ) : (
              <ul className="trade-lock-list">
                {lockReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
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
                    <article
                      className={
                        account.id === activeAccountId
                          ? "trade-account-option selected"
                          : "trade-account-option"
                      }
                      key={account.id}
                    >
                      <div>
                        <strong>{account.account_label}</strong>
                        <span>
                          {account.account_mode} / {account.trading_enabled ? "TRADING ON" : "READ ONLY"}
                        </span>
                      </div>
                      <div className="trade-account-actions">
                        <button onClick={() => selectAccountForTrading(account)}>Use in Ticket</button>
                        <button
                          onClick={() => {
                            selectAccountForTrading(account);
                            setBottomTab("positions");
                          }}
                        >
                          Exchange Window
                        </button>
                        <button
                          onClick={() => {
                            selectAccountForTrading(account);
                            focusAuditForAccount(account);
                          }}
                        >
                          Audit
                        </button>
                      </div>
                    </article>
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

        <section className="trade-preflight-card" id="pre-real-checklist">
          <div className="trade-preflight-head">
            <div>
              <span>Pre-Real Safety Checklist</span>
              <strong>小额资金测试前置检查</strong>
              <p>
                只汇总登录、账户、密钥、只读认证和审计证据。此清单不会开启真实交易，也不会发送订单。
              </p>
            </div>
            <div className="trade-preflight-status">
              <span className={preRealReady ? "ready" : "blocked"}>
                {preRealReady ? "READY FOR REVIEW" : "BLOCKED"}
              </span>
              <strong>
                {completedRequiredPreRealItems}/{requiredPreRealItems.length}
              </strong>
              <small>required checks</small>
            </div>
          </div>
          <div className="trade-preflight-actions">
            <button className="trade-ghost-button" onClick={refreshAccounts} disabled={!session.token || apiBusy}>
              Refresh Accounts
            </button>
            <button
              className="trade-ghost-button"
              onClick={() => activeAccount && focusAuditForAccount(activeAccount)}
              disabled={!activeAccount || !canViewAuditLogs || auditBusy}
            >
              Load Active Audit
            </button>
            <button
              className="trade-ghost-button"
              onClick={focusTestnetApprovalAudits}
              disabled={!canViewAuditLogs || auditBusy}
            >
              Load TESTNET Windows
            </button>
          </div>
          <div className="trade-checklist-grid">
            {preRealChecklist.map((item) => (
              <article className={`trade-check-item ${item.status}`} key={item.id}>
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.required ? "Required" : "Optional"}</span>
                </div>
                <p>{item.detail}</p>
                <b>{item.status.toUpperCase()}</b>
              </article>
            ))}
          </div>
          <div className={preRealReady ? "trade-next-action ready" : "trade-next-action"}>
            <span>Next action</span>
            <strong>{nextPreRealAction}</strong>
          </div>
        </section>

        <section className="trade-phase4-card" id="phase4-small-fund-review">
          <div className="trade-phase4-head">
            <div>
              <span>Phase 4 Control</span>
              <strong>Small-Fund Review Audit</strong>
              <p>
                Records a super-admin review for the selected REAL OKX account. This does not
                enable trading, authorize order submission, or expose API secrets.
              </p>
            </div>
            <div className={activePhase4Ready ? "phase4-status ready" : "phase4-status blocked"}>
              <span>{activePhase4Ready ? "READINESS PASS" : "READINESS BLOCKED"}</span>
              <strong>{latestPhase4ReviewAuditLog ? "REVIEW RECORDED" : "NO REVIEW AUDIT"}</strong>
            </div>
          </div>
          <div className="trade-phase4-grid">
            <label>
              <span>Max Notional Cap</span>
              <input
                inputMode="decimal"
                value={phase4MaxNotional}
                onChange={(event) => setPhase4MaxNotional(event.target.value)}
                placeholder="25"
              />
            </label>
            <label>
              <span>Current Password</span>
              <input
                type="password"
                value={phase4ReviewPassword}
                onChange={(event) => setPhase4ReviewPassword(event.target.value)}
                placeholder="Required for reauthentication"
              />
            </label>
            <button
              className="trade-secondary-button"
              onClick={loadPhase4Readiness}
              disabled={!activeAccount || apiBusy}
            >
              Load Readiness
            </button>
            <button
              className="trade-submit compact"
              onClick={recordPhase4SmallFundReview}
              disabled={!canRecordPhase4SmallFundReview || apiBusy}
            >
              Record Review Audit
            </button>
          </div>
          <div className="trade-phase4-actions">
            <button
              className="trade-ghost-button"
              onClick={focusPhase4ReviewAudits}
              disabled={!activeAccount || !canViewAuditLogs || auditBusy}
            >
              Load Review Audits
            </button>
            <span>
              Required acknowledgement: <strong>{phase4SmallFundReviewAck}</strong>
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
                    <span>{check.status}</span>
                  </div>
                  <p>{check.detail}</p>
                </article>
              ))}
            </div>
          ) : (
            <p className="trade-muted">
              Select a REAL OKX account and load readiness before recording a review audit.
            </p>
          )}
        </section>

        <section className="trade-phase4-card" id="phase4-real-order-window">
          <div className="trade-phase4-head">
            <div>
              <span>Phase 4 Control</span>
              <strong>REAL Small-Fund Order Window</strong>
              <p>
                Records the exact REAL order-window approval as append-only audit evidence.
                This still does not enable trading or submit an exchange order.
              </p>
            </div>
            <div className={latestPhase4OrderWindowAuditLog ? "phase4-status ready" : "phase4-status blocked"}>
              <span>{canRecordPhase4OrderWindow ? "READY TO RECORD" : "WINDOW LOCKED"}</span>
              <strong>{latestPhase4OrderWindowAuditLog ? "WINDOW RECORDED" : "NO WINDOW AUDIT"}</strong>
            </div>
          </div>
          <div className="trade-phase4-window-summary">
            <article>
              <span>Symbol</span>
              <strong>{normalizedPreviewSymbol}</strong>
            </article>
            <article>
              <span>Side</span>
              <strong className={orderSide === "BUY" ? "preview-buy" : "preview-sell"}>
                {orderSide}
              </strong>
            </article>
            <article>
              <span>Limit Price</span>
              <strong>{orderForm.orderType === "LIMIT" ? `${formatNumber(parsedPrice)} USDT` : "LIMIT required"}</strong>
            </article>
            <article>
              <span>Quantity</span>
              <strong>{Number.isFinite(parsedQuantity) ? parsedQuantity : "-"}</strong>
            </article>
            <article>
              <span>Max Notional</span>
              <strong>{formatNumber(estimatedNotional)} USDT</strong>
            </article>
          </div>
          <div className="trade-phase4-grid">
            <label>
              <span>Window Duration</span>
              <input
                inputMode="numeric"
                value={phase4OrderWindowDuration}
                onChange={(event) => setPhase4OrderWindowDuration(event.target.value)}
                placeholder="1-10 minutes"
              />
            </label>
            <label>
              <span>Current Password</span>
              <input
                type="password"
                value={phase4OrderWindowPassword}
                onChange={(event) => setPhase4OrderWindowPassword(event.target.value)}
                placeholder="Required for reauthentication"
              />
            </label>
            <button
              className="trade-secondary-button"
              onClick={focusPhase4OrderWindowAudits}
              disabled={!activeAccount || !canViewAuditLogs || auditBusy}
            >
              Load Window Audits
            </button>
            <button
              className="trade-submit compact"
              onClick={recordPhase4OrderWindowApproval}
              disabled={!canRecordPhase4OrderWindow || apiBusy}
            >
              Record Window Audit
            </button>
          </div>
          <div className="trade-phase4-actions">
            <span>
              Required acknowledgement: <strong>{phase4SmallFundOrderWindowAck}</strong>
            </span>
            <span>LIMIT only / review cap {formatNumber(phase4MaxNotionalValue)} USDT / no live order</span>
          </div>
        </section>

        <section className="trade-phase4-card" id="phase4-final-release-check">
          <div className="trade-phase4-head">
            <div>
              <span>Phase 4 Final Gate</span>
              <strong>Final Release Check Audit</strong>
              <p>
                Records the last pre-small-fund confirmation after the review and order-window
                audits exist. This is audit-only and still does not authorize or submit orders.
              </p>
            </div>
            <div className={latestPhase4FinalReleaseAuditLog ? "phase4-status ready" : "phase4-status blocked"}>
              <span>{canRecordPhase4FinalReleaseCheck ? "READY TO RECORD" : "FINAL GATE LOCKED"}</span>
              <strong>
                {latestPhase4FinalReleaseAuditLog ? "FINAL CHECK RECORDED" : "NO FINAL CHECK"}
              </strong>
            </div>
          </div>
          <div className="trade-phase4-window-summary">
            <article>
              <span>Review Audit</span>
              <strong>{latestPhase4ReviewAuditLog ? "RECORDED" : "MISSING"}</strong>
            </article>
            <article>
              <span>Window Audit</span>
              <strong>{latestPhase4OrderWindowAuditLog ? "RECORDED" : "MISSING"}</strong>
            </article>
            <article>
              <span>Final Notional</span>
              <strong>{formatNumber(estimatedNotional)} USDT</strong>
            </article>
            <article>
              <span>Trading Flag</span>
              <strong>{activeAccount?.trading_enabled ? "ON" : "OFF"}</strong>
            </article>
            <article>
              <span>Order Auth</span>
              <strong>AUDIT ONLY</strong>
            </article>
          </div>
          <div className="trade-final-confirmations">
            {[
              ["dedicatedAccount", "Dedicated test account is confirmed"],
              ["accountEmpty", "Account is empty or funded only with approved tiny test amount"],
              ["withdrawalsDisabled", "Withdrawal permission is disabled on the exchange API key"],
              ["deleteApiKeyAfterTest", "API key will be deleted after the test"],
              ["firstOrderStopReview", "First accepted order will stop the process for manual review"],
              ["noLiveOrderSubmission", "This button records audit only and will not submit an order"],
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
              <span>Current Password</span>
              <input
                type="password"
                value={phase4FinalPassword}
                onChange={(event) => setPhase4FinalPassword(event.target.value)}
                placeholder="Required for reauthentication"
              />
            </label>
            <button
              className="trade-secondary-button"
              onClick={focusPhase4FinalReleaseAudits}
              disabled={!activeAccount || !canViewAuditLogs || auditBusy}
            >
              Load Final Audits
            </button>
            <button
              className="trade-submit compact"
              onClick={recordPhase4FinalReleaseCheck}
              disabled={!canRecordPhase4FinalReleaseCheck || apiBusy}
            >
              Record Final Check
            </button>
          </div>
          <div className="trade-phase4-actions">
            <span>
              Required acknowledgement: <strong>{phase4FinalReleaseCheckAck}</strong>
            </span>
            <span>Requires review audit + order-window audit / no live order</span>
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
                        onClick={focusAuditForCurrentAccount}
                        disabled={!activeAccountId}
                      >
                        Active Account Read-only
                      </button>
                      <button
                        className="trade-secondary-button"
                        onClick={focusTestnetApprovalAudits}
                        disabled={!activeAccountId}
                      >
                        TESTNET Windows
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
                        <select
                          value={auditFilters.action}
                          onChange={(event) =>
                            setAuditFilters((current) => ({
                              ...current,
                              action: event.target.value,
                            }))
                          }
                        >
                          <option value="">All</option>
                          {auditActionOptions.map((action) => (
                            <option key={action} value={action}>
                              {action}
                            </option>
                          ))}
                        </select>
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
                        Created From
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
                        Created To
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
                      <button
                        className="trade-secondary-button"
                        onClick={exportAuditReport}
                        disabled={!auditLogs.length}
                      >
                        Export JSON
                      </button>
                    </div>
                    <div className="trade-audit-summary">
                      {["INFO", "OK", "WARNING", "ERROR"].map((severity) => (
                        <span key={severity}>
                          {severity} <strong>{auditSeverityCounts[severity] ?? 0}</strong>
                        </span>
                      ))}
                      <span>
                        TESTNET Windows <strong>{approvalAuditLogs.length}</strong>
                      </span>
                      <span>
                        Phase 4 Reviews <strong>{phase4ReviewAuditLogs.length}</strong>
                      </span>
                      <span>
                        REAL Windows <strong>{phase4OrderWindowAuditLogs.length}</strong>
                      </span>
                      <span>
                        Final Checks <strong>{phase4FinalReleaseAuditLogs.length}</strong>
                      </span>
                    </div>
                    {latestApprovalAuditLog ? (
                      <article className="trade-audit-highlight">
                        <div>
                          <span>Latest TESTNET approval window</span>
                          <strong>{formatDateTime(latestApprovalAuditLog.created_at)}</strong>
                        </div>
                        <dl>
                          <div>
                            <dt>Symbol</dt>
                            <dd>{String(latestApprovalAuditLog.payload.symbol ?? "-")}</dd>
                          </div>
                          <div>
                            <dt>Side</dt>
                            <dd>{String(latestApprovalAuditLog.payload.side ?? "-")}</dd>
                          </div>
                          <div>
                            <dt>Order auth</dt>
                            <dd>
                              {latestApprovalAuditLog.payload.order_submission_authorized === true
                                ? "AUTHORIZED"
                                : "AUDIT ONLY"}
                            </dd>
                          </div>
                          <div>
                            <dt>Expires</dt>
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
                              {selectedApprovalPayload ? (
                                <div className="trade-approval-grid">
                                  <div>
                                    <span>Symbol</span>
                                    <strong>{String(selectedApprovalPayload.symbol ?? "-")}</strong>
                                  </div>
                                  <div>
                                    <span>Side</span>
                                    <strong>{String(selectedApprovalPayload.side ?? "-")}</strong>
                                  </div>
                                  <div>
                                    <span>Max Quantity</span>
                                    <strong>{String(selectedApprovalPayload.max_quantity ?? "-")}</strong>
                                  </div>
                                  <div>
                                    <span>Max Notional</span>
                                    <strong>{String(selectedApprovalPayload.max_notional ?? "-")}</strong>
                                  </div>
                                  <div>
                                    <span>Submission</span>
                                    <strong>
                                      {selectedApprovalPayload.order_submission_authorized === true
                                        ? "AUTHORIZED"
                                        : "AUDIT ONLY"}
                                    </strong>
                                  </div>
                                  <div>
                                    <span>Trading Flags</span>
                                    <strong>
                                      {selectedApprovalPayload.trading_flags_changed === true
                                        ? "CHANGED"
                                        : "UNCHANGED"}
                                    </strong>
                                  </div>
                                </div>
                              ) : null}
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
                <span>Order Preview</span>
                <h2 id="order-preview-title">
                  {activeSymbol} {orderSide}
                </h2>
              </div>
              <button
                aria-label="Close order preview"
                className="trade-icon-button"
                onClick={() => setIsOrderPreviewOpen(false)}
              >
                X
              </button>
            </header>
            <div className="trade-preview-warning">
              <strong>{canRecordTestnetOrderWindow ? "Testnet Approval Window" : orderLocked ? "Locked" : "Preview Only"}</strong>
              <span>
                {selectedAccountRoute} This screen never submits an exchange order. TESTNET approval records
                an audit-only window after password reauthentication.
              </span>
            </div>
            <dl className="trade-preview-grid">
              <div>
                <dt>Exchange</dt>
                <dd>{activeExchangeProfile.label}</dd>
              </div>
              <div>
                <dt>Account</dt>
                <dd>{activeAccount?.account_label ?? "-"}</dd>
              </div>
              <div>
                <dt>Mode</dt>
                <dd>{activeAccount?.account_mode ?? "-"}</dd>
              </div>
              <div>
                <dt>Account Status</dt>
                <dd>{activeAccountHealth}</dd>
              </div>
              <div>
                <dt>Order Type</dt>
                <dd>{orderForm.orderType}</dd>
              </div>
              <div>
                <dt>Side</dt>
                <dd className={orderSide === "BUY" ? "preview-buy" : "preview-sell"}>{orderSide}</dd>
              </div>
              <div>
                <dt>Reference Price</dt>
                <dd>{formatNumber(referencePrice)} USDT</dd>
              </div>
              <div>
                <dt>Quantity</dt>
                <dd>{Number.isFinite(parsedQuantity) ? parsedQuantity : "-"}</dd>
              </div>
              <div>
                <dt>Estimated Notional</dt>
                <dd>{formatNumber(estimatedNotional)} USDT</dd>
              </div>
            </dl>
            <div className="trade-route-panel">
              <span>Client Order ID Preview</span>
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
                <span>Testnet Order Window</span>
                <strong>Audit only / 5 minutes / no trading flags changed</strong>
                {testnetWindowReasons.length > 0 ? (
                  <ul className="trade-lock-list compact">
                    {testnetWindowReasons.map((reason) => (
                      <li key={reason}>{reason}</li>
                    ))}
                  </ul>
                ) : (
                  <label className="trade-field">
                    Current password
                    <input
                      type="password"
                      value={orderApprovalPassword}
                      onChange={(event) => setOrderApprovalPassword(event.target.value)}
                      placeholder="Required for approval audit"
                    />
                  </label>
                )}
              </div>
            )}
            <pre className="trade-preview-json">{prettyJson(orderPreviewPayload)}</pre>
            <footer>
              <button className="trade-secondary-button" onClick={focusAuditForCurrentAccount}>
                Related Audit
              </button>
              <button className="trade-secondary-button" onClick={() => setIsOrderPreviewOpen(false)}>
                Cancel
              </button>
              {activeAccount?.account_mode === "TESTNET" && activeExchange !== "mock" && (
                <button
                  className="trade-secondary-button"
                  disabled={!canRecordTestnetOrderWindow || apiBusy}
                  onClick={recordTestnetOrderWindowApproval}
                >
                  Record Testnet Window
                </button>
              )}
              <button className="trade-submit compact" disabled={orderLocked} onClick={confirmOrderPreview}>
                Confirm Preview
              </button>
            </footer>
          </section>
        </div>
      )}
    </main>
  );
}
