"use client";

import QRCode from "qrcode";
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

type MfaStatus = {
  enabled: boolean;
  enrollmentPending: boolean;
};

type ExchangeAccount = {
  id: string;
  exchange_name: "binance" | "bybit" | "okx" | "mock";
  account_label: string;
  account_mode: "SIMULATION" | "TESTNET" | "REAL";
  trading_enabled: boolean;
  is_active: boolean;
};

type TestnetOrderAdmissionCheck = {
  name: string;
  status: "PASS" | "BLOCKED";
  required: boolean;
  detail: string;
};

type TestnetOrderAdmissionReport = {
  exchange_account_id: string;
  exchange_name: ExchangeAccount["exchange_name"];
  account_mode: ExchangeAccount["account_mode"];
  overall_status: "PASS" | "BLOCKED";
  read_only: boolean;
  order_submission_authorized: boolean;
  gate_reasons: string[];
  checks: TestnetOrderAdmissionCheck[];
};

type Phase4ReadinessCheck = {
  name: string;
  status: "PASS" | "BLOCKED";
  required: boolean;
  detail: string;
};

type Phase4ReadinessReport = {
  exchange_account_id: string;
  exchange_name: ExchangeAccount["exchange_name"];
  account_mode: ExchangeAccount["account_mode"];
  overall_status: "PASS" | "BLOCKED";
  read_only: boolean;
  order_submission_authorized: boolean;
  checks: Phase4ReadinessCheck[];
  gate_reasons: string[];
};

type TestnetOrderWindowPlan = {
  exchange_account_id: string;
  status: "READY_FOR_SEPARATE_APPROVAL" | "BLOCKED";
  state: {
    exchange_name: ExchangeAccount["exchange_name"];
    account_mode: ExchangeAccount["account_mode"];
    testnet_adapters_enabled: boolean;
    exchange_account_trading_enabled: boolean;
    risk_settings_exist: boolean;
    risk_trading_enabled: boolean;
    api_key_configured: boolean;
  };
  blocked_reasons: string[];
  required_operator_steps: string[];
  mutations_allowed: boolean;
  order_submission_authorized: boolean;
};

type TestnetOrderWindowApproval = {
  audit_log_id: string;
  exchange_account_id: string;
  exchange_name: ExchangeAccount["exchange_name"];
  symbol: string;
  side: "BUY" | "SELL";
  max_quantity: string;
  max_notional: string;
  duration_minutes: number;
  order_submission_authorized: boolean;
  trading_flags_changed: boolean;
};

type TimedTestnetOrderWindowApproval = TestnetOrderWindowApproval & {
  approvedAtMs: number;
};

type TestnetOrderSubmitResponse = {
  exchange_account_id: string;
  exchange_name: ExchangeAccount["exchange_name"];
  client_order_id: string;
  request_method: string;
  request_path: string;
  approval_audit_log_id: string;
  approval_expires_at: string;
  exchange_response: Record<string, unknown>;
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

const SESSION_TOKEN_STORAGE_KEY = "trading_platform_token";

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
  const [apiBase] = useState(resolveApiBase);
  const [session, setSession] = useState<SessionState>(emptySession);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [storageLocations, setStorageLocations] = useState<StorageLocation[]>([]);
  const [busy, setBusy] = useState(false);
  const [manualLogin, setManualLogin] = useState({
    usernameOrEmail: "",
    password: "",
    mfaCode: "",
  });
  const [passwordChange, setPasswordChange] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [mfaStatus, setMfaStatus] = useState<MfaStatus>({
    enabled: false,
    enrollmentPending: false,
  });
  const [mfaForm, setMfaForm] = useState({
    password: "",
    code: "",
  });
  const [mfaEnrollment, setMfaEnrollment] = useState({
    qrDataUrl: "",
    manualEntryKey: "",
    recoveryCodes: [] as string[],
  });
  const [exchangeAccounts, setExchangeAccounts] = useState<ExchangeAccount[]>([]);
  const [testnetAccountId, setTestnetAccountId] = useState("");
  const [testnetAdmissionReport, setTestnetAdmissionReport] =
    useState<TestnetOrderAdmissionReport | null>(null);
  const [phase4ReadinessReport, setPhase4ReadinessReport] =
    useState<Phase4ReadinessReport | null>(null);
  const [testnetOrderWindowPlan, setTestnetOrderWindowPlan] =
    useState<TestnetOrderWindowPlan | null>(null);
  const [testnetForm, setTestnetForm] = useState({
    accountMode: "TESTNET" as "TESTNET" | "REAL",
    exchangeName: "binance" as "binance" | "bybit" | "okx",
    accountLabel: "",
    apiKey: "",
    apiSecret: "",
    passphrase: "",
    password: "",
  });
  const [testnetWindowApprovalForm, setTestnetWindowApprovalForm] = useState({
    symbol: "BTCUSDT",
    side: "BUY" as "BUY" | "SELL",
    maxQuantity: "0.001",
    maxNotional: "100",
    durationMinutes: "5",
  });
  const [testnetOrderSubmitForm, setTestnetOrderSubmitForm] = useState({
    symbol: "BTCUSDT",
    side: "BUY" as "BUY" | "SELL",
    quantity: "0.0001",
    price: "10000",
    clientOrderId: "",
  });
  const [lastTestnetApproval, setLastTestnetApproval] =
    useState<TimedTestnetOrderWindowApproval | null>(null);
  const [nowMs, setNowMs] = useState(0);
  const [testnetKeyConfigured, setTestnetKeyConfigured] = useState(false);
  const [restoredStoredSession, setRestoredStoredSession] = useState(false);

  useEffect(() => {
    setNowMs(Date.now());
    const timerId = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(timerId);
  }, []);

  const apiRoot = useMemo(() => `${apiBase}/api/v1`, [apiBase]);

  useEffect(() => {
    if (restoredStoredSession || session.token || typeof window === "undefined") {
      return;
    }
    const token = window.localStorage.getItem(SESSION_TOKEN_STORAGE_KEY);
    setRestoredStoredSession(true);
    if (!token) {
      return;
    }
    void loadAuthenticatedSession(token).catch(() => {
      window.localStorage.removeItem(SESSION_TOKEN_STORAGE_KEY);
    });
  }, [apiRoot, restoredStoredSession, session.token]);

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
    extraHeaders: Record<string, string> = {},
  ): Promise<ApiResult> {
    const response = await fetch(`${apiRoot}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        ...(payload ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...extraHeaders,
      },
      body: payload ? JSON.stringify(payload) : undefined,
    });
    const text = await response.text();
    const body = text ? JSON.parse(text) : null;
    if (response.status !== expectedStatus) {
      if (response.status === 401 && token) {
        clearSession();
        throw new Error("登录会话已失效，请重新登录");
      }
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
    let nextMfaStatus: MfaStatus = {
      enabled: false,
      enrollmentPending: false,
    };
    const accountResult = await apiRequest(
      "GET",
      "/exchange-accounts",
      undefined,
      token,
    );
    if (!Array.isArray(accountResult)) {
      throw new Error("交易所账户返回格式异常");
    }
    const accounts = accountResult as ExchangeAccount[];
    const firstReadOnlyAccount = accounts.find(
      (account) =>
        account.account_mode === "REAL" || account.account_mode === "TESTNET",
    );
    let firstReadOnlyKeyConfigured = false;
    if (firstReadOnlyAccount) {
      const metadata = requireObject(
        await apiRequest(
          "GET",
          `/exchange-accounts/${firstReadOnlyAccount.id}/api-key`,
          undefined,
          token,
        ),
        "测试网密钥状态",
      );
      firstReadOnlyKeyConfigured = Boolean(metadata.configured);
    }

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

      const mfaResult = requireObject(
        await apiRequest("GET", "/users/me/mfa", undefined, token),
        "MFA 状态",
      );
      nextMfaStatus = {
        enabled: Boolean(mfaResult.enabled),
        enrollmentPending: Boolean(mfaResult.enrollment_pending),
      };
    }

    setSession((current) => ({
      ...current,
      token,
      userId: String(profile.id),
      username: String(profile.username),
      role,
    }));
    if (typeof window !== "undefined") {
      window.localStorage.setItem(SESSION_TOKEN_STORAGE_KEY, token);
    }
    setStorageLocations(locations);
    setMfaStatus(nextMfaStatus);
    setExchangeAccounts(accounts);
    setTestnetAccountId(firstReadOnlyAccount?.id ?? "");
    setTestnetAdmissionReport(null);
    setPhase4ReadinessReport(null);
    setTestnetOrderWindowPlan(null);
    setLastTestnetApproval(null);
    setTestnetKeyConfigured(firstReadOnlyKeyConfigured);
    if (firstReadOnlyAccount && firstReadOnlyAccount.exchange_name !== "mock") {
      setTestnetForm((current) => ({
        ...current,
        accountMode: firstReadOnlyAccount.account_mode as "TESTNET" | "REAL",
        exchangeName: firstReadOnlyAccount.exchange_name as
          | "binance"
          | "bybit"
          | "okx",
      }));
    }
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
            ...(manualLogin.mfaCode ? { mfa_code: manualLogin.mfaCode } : {}),
          },
          "",
        ),
        "登录",
      );
      const profile = await loadAuthenticatedSession(
        String(tokenResponse.access_token),
      );
      setManualLogin((current) => ({
        ...current,
        password: "",
        mfaCode: "",
      }));
      return {
        username: profile.username,
        user_id: profile.id,
        role: profile.role,
        token_loaded: true,
      };
    });
  }

  function clearSession() {
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(SESSION_TOKEN_STORAGE_KEY);
    }
    setSession(emptySession);
    setStorageLocations([]);
    setManualLogin((current) => ({
      ...current,
      password: "",
      mfaCode: "",
    }));
    setPasswordChange({
      currentPassword: "",
      newPassword: "",
      confirmPassword: "",
    });
    setMfaStatus({ enabled: false, enrollmentPending: false });
    setMfaForm({ password: "", code: "" });
    setMfaEnrollment({
      qrDataUrl: "",
      manualEntryKey: "",
      recoveryCodes: [],
    });
    setExchangeAccounts([]);
    setTestnetAccountId("");
    setTestnetAdmissionReport(null);
    setPhase4ReadinessReport(null);
    setTestnetOrderWindowPlan(null);
    setLastTestnetApproval(null);
    setTestnetKeyConfigured(false);
    setTestnetForm({
      accountMode: "TESTNET",
      exchangeName: "binance",
      accountLabel: "",
      apiKey: "",
      apiSecret: "",
      passphrase: "",
      password: "",
    });
  }

  async function startMfaEnrollment() {
    await runStep("开始 MFA 配置", async () => {
      const reauthentication = requireObject(
        await apiRequest("POST", "/auth/reauthenticate", {
          password: mfaForm.password,
        }),
        "密码再认证",
      );
      const reauthenticationToken = String(
        reauthentication.reauthentication_token,
      );
      const enrollment = requireObject(
        await apiRequest(
          "POST",
          "/users/me/mfa/enroll",
          undefined,
          session.token,
          200,
          {
            "X-Reauthentication-Token": reauthenticationToken,
          },
        ),
        "MFA 注册",
      );
      const provisioningUri = String(enrollment.provisioning_uri);
      const qrDataUrl = await QRCode.toDataURL(provisioningUri, {
        margin: 1,
        width: 200,
      });
      setMfaStatus({ enabled: false, enrollmentPending: true });
      setMfaEnrollment({
        qrDataUrl,
        manualEntryKey: String(enrollment.manual_entry_key),
        recoveryCodes: [],
      });
      return { enrollment_started: true };
    });
  }

  async function confirmMfaEnrollment() {
    await runStep("启用 MFA", async () => {
      const reauthentication = requireObject(
        await apiRequest("POST", "/auth/reauthenticate", {
          password: mfaForm.password,
        }),
        "密码再认证",
      );
      const confirmation = requireObject(
        await apiRequest(
          "POST",
          "/users/me/mfa/confirm",
          { code: mfaForm.code },
          session.token,
          200,
          {
            "X-Reauthentication-Token": String(
              reauthentication.reauthentication_token,
            ),
          },
        ),
        "MFA 确认",
      );
      const recoveryCodes = Array.isArray(confirmation.recovery_codes)
        ? confirmation.recovery_codes.map(String)
        : [];
      setMfaStatus({ enabled: true, enrollmentPending: false });
      setMfaEnrollment((current) => ({
        ...current,
        recoveryCodes,
      }));
      setMfaForm({ password: "", code: "" });
      return {
        mfa_enabled: true,
        recovery_code_count: recoveryCodes.length,
        login_required: true,
      };
    });
  }

  async function disableMfa() {
    await runStep("关闭 MFA", async () => {
      const reauthentication = requireObject(
        await apiRequest("POST", "/auth/reauthenticate", {
          password: mfaForm.password,
        }),
        "密码再认证",
      );
      const result = await apiRequest(
        "POST",
        "/users/me/mfa/disable",
        { code: mfaForm.code },
        session.token,
        200,
        {
          "X-Reauthentication-Token": String(
            reauthentication.reauthentication_token,
          ),
        },
      );
      clearSession();
      return { result, session_cleared: true, login_required: true };
    });
  }

  async function changeOwnPassword() {
    if (passwordChange.newPassword !== passwordChange.confirmPassword) {
      appendLog("修改密码", false, "两次输入的新密码不一致");
      return;
    }
    if (passwordChange.newPassword.length < 16) {
      appendLog("修改密码", false, "新密码至少需要 16 个字符");
      return;
    }
    await runStep("修改密码", async () => {
      const result = await apiRequest("POST", "/users/me/password", {
        current_password: passwordChange.currentPassword,
        new_password: passwordChange.newPassword,
      });
      clearSession();
      return { result, session_cleared: true, login_required: true };
    });
  }

  async function createReauthenticationToken(password: string) {
    const result = requireObject(
      await apiRequest("POST", "/auth/reauthenticate", { password }),
      "密码再认证",
    );
    return String(result.reauthentication_token);
  }

  async function createTestnetAccount() {
    const mode = testnetForm.accountMode;
    const exchangeName = mode === "REAL" ? "okx" : testnetForm.exchangeName;
    await runStep(`创建 ${mode} 只读账户`, async () => {
      const account = requireObject(
        await apiRequest("POST", "/exchange-accounts", {
          exchange_name: exchangeName,
          account_label:
            testnetForm.accountLabel.trim() ||
            `${exchangeName.toUpperCase()} ${mode === "REAL" ? "Production Read Only" : "Testnet"}`,
          account_mode: mode,
          trading_enabled: false,
        }, session.token, 201),
        `创建 ${mode} 只读账户`,
      ) as ExchangeAccount;
      setExchangeAccounts((current) => [...current, account]);
      setTestnetAccountId(account.id);
      setTestnetAdmissionReport(null);
      setPhase4ReadinessReport(null);
      setTestnetOrderWindowPlan(null);
      setLastTestnetApproval(null);
      setTestnetKeyConfigured(false);
      return {
        account_id: account.id,
        exchange: account.exchange_name,
        mode: account.account_mode,
        trading_enabled: account.trading_enabled,
      };
    });
  }

  async function selectTestnetAccount(accountId: string) {
    setTestnetAccountId(accountId);
    setTestnetAdmissionReport(null);
    setPhase4ReadinessReport(null);
    setTestnetOrderWindowPlan(null);
    setLastTestnetApproval(null);
    setTestnetKeyConfigured(false);
    const selectedAccount = exchangeAccounts.find(
      (account) => account.id === accountId,
    );
    if (selectedAccount && selectedAccount.exchange_name !== "mock") {
      setTestnetForm((current) => ({
        ...current,
        accountMode: selectedAccount.account_mode as "TESTNET" | "REAL",
        exchangeName: selectedAccount.exchange_name as "binance" | "bybit" | "okx",
      }));
    }
    if (!accountId) {
      return;
    }
    await runStep("读取测试网密钥状态", async () => {
      const metadata = requireObject(
        await apiRequest("GET", `/exchange-accounts/${accountId}/api-key`),
        "密钥状态",
      );
      setTestnetKeyConfigured(Boolean(metadata.configured));
      return {
        account_id: accountId,
        configured: Boolean(metadata.configured),
        has_passphrase: Boolean(metadata.has_passphrase),
      };
    });
  }

  async function saveTestnetCredentials() {
    if (!testnetAccountId) {
      appendLog("保存只读 API Key", false, "请先创建或选择只读账户");
      return;
    }
    if (testnetForm.exchangeName === "okx" && !testnetForm.passphrase) {
      appendLog("保存只读 API Key", false, "OKX API 必须填写 Passphrase");
      return;
    }
    const credentials = {
      apiKey: testnetForm.apiKey,
      apiSecret: testnetForm.apiSecret,
      passphrase: testnetForm.passphrase,
      password: testnetForm.password,
    };
    try {
      await runStep("保存只读 API Key", async () => {
        const reauthenticationToken = await createReauthenticationToken(
          credentials.password,
        );
        const metadata = await apiRequest(
          "POST",
          `/exchange-accounts/${testnetAccountId}/api-key`,
          {
            api_key: credentials.apiKey,
            api_secret: credentials.apiSecret,
            passphrase: credentials.passphrase || null,
          },
          session.token,
          200,
          { "X-Reauthentication-Token": reauthenticationToken },
        );
        setTestnetKeyConfigured(true);
        setTestnetAdmissionReport(null);
        setPhase4ReadinessReport(null);
        setTestnetOrderWindowPlan(null);
        setLastTestnetApproval(null);
        return metadata;
      });
    } finally {
      setTestnetForm((current) => ({
        ...current,
        apiKey: "",
        apiSecret: "",
        passphrase: "",
        password: "",
      }));
    }
  }

  async function runTestnetReadOnlyCheck() {
    if (!testnetAccountId) {
      appendLog("只读认证", false, "请先创建或选择只读账户");
      return;
    }
    const password = testnetForm.password;
    try {
      await runStep(
        selectedTestnetAccount?.account_mode === "REAL"
          ? "OKX 正式 API 只读认证"
          : "测试网只读认证",
        async () => {
          const reauthenticationToken = await createReauthenticationToken(password);
          return apiRequest(
            "POST",
            `/exchange-accounts/${testnetAccountId}/${
              selectedTestnetAccount?.account_mode === "REAL"
                ? "real-read-only-check"
                : "testnet-read-only-check"
            }`,
            undefined,
            session.token,
            200,
            { "X-Reauthentication-Token": reauthenticationToken },
          );
        },
      );
    } finally {
      setTestnetForm((current) => ({ ...current, password: "" }));
    }
  }

  async function runTestnetOrderAdmissionCheck() {
    if (!testnetAccountId) {
      appendLog("TESTNET 下单准入自检", false, "请先创建或选择 TESTNET 账户");
      return;
    }
    if (selectedTestnetAccount?.account_mode !== "TESTNET") {
      appendLog("TESTNET 下单准入自检", false, "只允许 TESTNET 账户运行下单准入自检");
      return;
    }
    await runStep("TESTNET 下单准入自检", async () => {
      const query = new URLSearchParams({
        exchange_account_id: testnetAccountId,
      });
      const report = requireObject(
        await apiRequest("GET", `/orders/testnet/admission-check?${query.toString()}`),
        "TESTNET 下单准入自检",
      ) as unknown as TestnetOrderAdmissionReport;
      setTestnetAdmissionReport(report);
      return {
        overall_status: report.overall_status,
        read_only: report.read_only,
        order_submission_authorized: report.order_submission_authorized,
        blocked_checks: report.checks
          .filter((check) => check.status === "BLOCKED")
          .map((check) => check.name),
      };
    });
  }

  async function runPhase4ReadinessCheck() {
    if (!testnetAccountId) {
      appendLog("Phase 4 REAL readiness", false, "Select a REAL account first");
      return;
    }
    if (selectedTestnetAccount?.account_mode !== "REAL") {
      appendLog(
        "Phase 4 REAL readiness",
        false,
        "Phase 4 readiness is only available for REAL accounts",
      );
      return;
    }
    await runStep("Phase 4 REAL readiness", async () => {
      const report = requireObject(
        await apiRequest(
          "GET",
          `/exchange-accounts/${testnetAccountId}/phase4-readiness`,
        ),
        "Phase 4 REAL readiness",
      ) as unknown as Phase4ReadinessReport;
      setPhase4ReadinessReport(report);
      return {
        overall_status: report.overall_status,
        read_only: report.read_only,
        order_submission_authorized: report.order_submission_authorized,
        blocked_checks: report.gate_reasons,
      };
    });
  }

  async function runTestnetOrderWindowPlan() {
    if (!testnetAccountId) {
      appendLog("TESTNET order window plan", false, "Select a TESTNET account first");
      return;
    }
    if (selectedTestnetAccount?.account_mode !== "TESTNET") {
      appendLog(
        "TESTNET order window plan",
        false,
        "Only TESTNET accounts can run the window plan",
      );
      return;
    }
    await runStep("TESTNET order window plan", async () => {
      const query = new URLSearchParams({
        exchange_account_id: testnetAccountId,
      });
      const plan = requireObject(
        await apiRequest("GET", `/orders/testnet/window-plan?${query.toString()}`),
        "TESTNET order window plan",
      ) as unknown as TestnetOrderWindowPlan;
      setTestnetOrderWindowPlan(plan);
      return {
        status: plan.status,
        mutations_allowed: plan.mutations_allowed,
        order_submission_authorized: plan.order_submission_authorized,
        blocked_reasons: plan.blocked_reasons,
      };
    });
  }

  async function recordTestnetOrderWindowApproval() {
    if (!testnetAccountId) {
      appendLog("TESTNET order window approval", false, "Select a TESTNET account first");
      return;
    }
    if (selectedTestnetAccount?.account_mode !== "TESTNET") {
      appendLog(
        "TESTNET order window approval",
        false,
        "Only TESTNET accounts can record an order window approval",
      );
      return;
    }
    await runStep("TESTNET order window approval", async () => {
      const approval = requireObject(
        await apiRequest("POST", "/orders/testnet/window-approval", {
          exchange_account_id: testnetAccountId,
          symbol: testnetWindowApprovalForm.symbol.trim().toUpperCase(),
          side: testnetWindowApprovalForm.side,
          max_quantity: testnetWindowApprovalForm.maxQuantity,
          max_notional: testnetWindowApprovalForm.maxNotional,
          duration_minutes: Number(testnetWindowApprovalForm.durationMinutes),
          acknowledgement: "APPROVE_TESTNET_ORDER_WINDOW_ONLY",
        }),
        "TESTNET order window approval",
      ) as unknown as TestnetOrderWindowApproval;
      setLastTestnetApproval({
        ...approval,
        approvedAtMs: Date.now(),
      });
      return {
        audit_log_id: approval.audit_log_id,
        exchange_account_id: approval.exchange_account_id,
        symbol: approval.symbol,
        side: approval.side,
        max_quantity: approval.max_quantity,
        max_notional: approval.max_notional,
        duration_minutes: approval.duration_minutes,
        order_submission_authorized: approval.order_submission_authorized,
        trading_flags_changed: approval.trading_flags_changed,
      };
    });
  }

  async function submitTestnetOrder() {
    if (!testnetAccountId) {
      appendLog("TESTNET order submit", false, "Select a TESTNET account first");
      return;
    }
    if (selectedTestnetAccount?.account_mode !== "TESTNET") {
      appendLog(
        "TESTNET order submit",
        false,
        "Only TESTNET accounts can submit testnet orders",
      );
      return;
    }
    if (!lastTestnetApproval || !testnetApprovalRemainingSeconds) {
      appendLog(
        "TESTNET order submit",
        false,
        "A non-expired order window approval is required",
      );
      return;
    }
    await runStep("TESTNET order submit", async () => {
      const result = requireObject(
        await apiRequest("POST", "/orders/testnet/submit", {
          exchange_account_id: testnetAccountId,
          symbol: testnetOrderSubmitForm.symbol.trim().toUpperCase(),
          side: testnetOrderSubmitForm.side,
          order_type: "LIMIT",
          quantity: testnetOrderSubmitForm.quantity,
          price: testnetOrderSubmitForm.price,
          client_order_id:
            testnetOrderSubmitForm.clientOrderId.trim() ||
            `ui-testnet-${Date.now()}`,
          manual_testnet_order_enable_confirmed: true,
        }),
        "TESTNET order submit",
      ) as unknown as TestnetOrderSubmitResponse;
      return {
        exchange_account_id: result.exchange_account_id,
        exchange_name: result.exchange_name,
        client_order_id: result.client_order_id,
        request_method: result.request_method,
        request_path: result.request_path,
        approval_audit_log_id: result.approval_audit_log_id,
        approval_expires_at: result.approval_expires_at,
        exchange_response: result.exchange_response,
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
  const testnetAccounts = exchangeAccounts.filter(
    (account) =>
      account.account_mode === "TESTNET" || account.account_mode === "REAL",
  );
  const selectedTestnetAccount = testnetAccounts.find(
    (account) => account.id === testnetAccountId,
  );
  const sessionStatus = session.token ? "已登录" : "未登录";
  const selectedAccountMode = selectedTestnetAccount?.account_mode ?? "未选择";
  const selectedExchange = selectedTestnetAccount?.exchange_name?.toUpperCase() ?? "-";
  const latestLog = logs[0];
  const latestLogStatus = latestLog ? (latestLog.ok ? "PASS" : "FAIL") : "待执行";
  const mockAccountReady = Boolean(session.accountId);
  const exchangeAccountCount = exchangeAccounts.length;
  const failedLogCount = logs.filter((entry) => !entry.ok).length;
  const admissionPassedCount =
    testnetAdmissionReport?.checks.filter((check) => check.status === "PASS")
      .length ?? 0;
  const admissionBlockedCount =
    testnetAdmissionReport?.checks.filter((check) => check.status === "BLOCKED")
      .length ?? 0;
  const phase4PassedCount =
    phase4ReadinessReport?.checks.filter((check) => check.status === "PASS")
      .length ?? 0;
  const phase4BlockedCount =
    phase4ReadinessReport?.checks.filter((check) => check.status === "BLOCKED")
      .length ?? 0;
  const testnetWindowReady =
    testnetAdmissionReport?.overall_status === "PASS" &&
    testnetOrderWindowPlan?.status === "READY_FOR_SEPARATE_APPROVAL";
  const testnetApprovalExpiresAtMs = lastTestnetApproval
    ? lastTestnetApproval.approvedAtMs +
      lastTestnetApproval.duration_minutes * 60 * 1000
    : null;
  const testnetApprovalRemainingSeconds =
    testnetApprovalExpiresAtMs && nowMs
      ? Math.max(0, Math.ceil((testnetApprovalExpiresAtMs - nowMs) / 1000))
      : null;
  const testnetApprovalActive =
    testnetApprovalRemainingSeconds !== null && testnetApprovalRemainingSeconds > 0;
  const canSubmitTestnetOrder =
    Boolean(session.token) &&
    selectedTestnetAccount?.account_mode === "TESTNET" &&
    testnetApprovalActive &&
    Boolean(testnetOrderSubmitForm.symbol.trim()) &&
    Boolean(testnetOrderSubmitForm.quantity.trim()) &&
    Boolean(testnetOrderSubmitForm.price.trim());
  const testnetApprovalRemainingLabel =
    testnetApprovalRemainingSeconds === null
      ? "-"
      : `${Math.floor(testnetApprovalRemainingSeconds / 60)}m ${
          testnetApprovalRemainingSeconds % 60
        }s`;
  const testnetApprovalExpiresAtLabel =
    testnetApprovalExpiresAtMs === null
      ? "-"
      : new Date(testnetApprovalExpiresAtMs).toLocaleTimeString();
  const testnetOrderWindowPreview = [
    {
      label: "账户",
      value: selectedTestnetAccount?.account_label ?? "未选择",
    },
    {
      label: "交易所",
      value: selectedExchange,
    },
    {
      label: "交易对",
      value: testnetWindowApprovalForm.symbol.trim().toUpperCase() || "-",
    },
    {
      label: "方向",
      value: testnetWindowApprovalForm.side,
    },
    {
      label: "最大数量",
      value: testnetWindowApprovalForm.maxQuantity || "-",
    },
    {
      label: "最大名义价值",
      value: testnetWindowApprovalForm.maxNotional || "-",
    },
  ];

  return (
    <main className="terminal-shell">
      <aside className="console-sidebar" aria-label="控制台导航">
        <a className="sidebar-brand" href="#overview">
          <span>CT</span>
          <strong>Copy Trading</strong>
        </a>
        <nav className="sidebar-nav">
          <a href="#overview">总览</a>
          <a href="#mock-flow">Mock 交易</a>
          <a href="#session">会话</a>
          <a href="#security">安全</a>
          <a href="#exchange-accounts">交易所账户</a>
          <a href="#testnet-window">测试网窗口</a>
          {session.role === "super_admin" && <a href="#storage">存储</a>}
          <a href="#audit-log">执行日志</a>
        </nav>
        <div className="sidebar-safety">
          <span>运行边界</span>
          <strong>NO LIVE ORDER</strong>
          <p>测试期仅允许 Mock 执行，真实 API 只读验证。</p>
        </div>
      </aside>

      <div className="terminal-main">
        <header className="topbar">
          <div>
            <div className="brand">多租户加密货币交易执行与跟单平台</div>
            <div className="subtle">Ubuntu 集成测试控制台</div>
          </div>
          <div className="topbar-actions">
            <span className="status">SIMULATION / TESTNET / REAL READ ONLY</span>
            <a className="topbar-login-link" href="/login">
              登录页
            </a>
          </div>
        </header>

      <div className="main console-layout" id="overview">
        <section className="panel hero-panel">
          <div>
            <span className="hero-kicker">V1.0 Integration Console</span>
            <h1>交易执行测试工作台</h1>
            <p>
              当前页面支持 MockExchange 模拟执行与 TESTNET 只读认证。测试网账户始终关闭交易，不提供下单操作。
            </p>
          </div>
          <div className="api-chip">API {apiRoot}</div>
        </section>

        <section className="overview-strip" aria-label="测试状态总览">
          <div>
            <span>会话</span>
            <strong>{sessionStatus}</strong>
          </div>
          <div>
            <span>角色</span>
            <strong>{session.role || "-"}</strong>
          </div>
          <div>
            <span>账户模式</span>
            <strong>{selectedAccountMode}</strong>
          </div>
          <div>
            <span>交易所</span>
            <strong>{selectedExchange}</strong>
          </div>
          <div>
            <span>最新结果</span>
            <strong className={latestLog?.ok === false ? "overview-fail" : "overview-pass"}>
              {latestLogStatus}
            </strong>
          </div>
        </section>

        <section className="safety-strip" aria-label="安全边界">
          <div>
            <strong>当前测试边界</strong>
            <span>Mock 可执行；TESTNET/REAL 只读验证；测试网订单窗口只记录审批审计，不提交订单。</span>
          </div>
          <span className="safety-badge">NO LIVE ORDER</span>
        </section>

        <section className="market-metrics" aria-label="测试模块状态">
          <article>
            <span>Mock 执行账户</span>
            <strong>{mockAccountReady ? "READY" : "WAITING"}</strong>
            <em>{session.accountId || "未创建"}</em>
          </article>
          <article>
            <span>交易所账户</span>
            <strong>{exchangeAccountCount}</strong>
            <em>TESTNET / REAL read-only</em>
          </article>
          <article>
            <span>密钥状态</span>
            <strong>{testnetKeyConfigured ? "CONFIGURED" : "NOT SET"}</strong>
            <em>Secret 不返回前端</em>
          </article>
          <article>
            <span>日志风险</span>
            <strong className={failedLogCount > 0 ? "overview-fail" : "overview-pass"}>
              {failedLogCount}
            </strong>
            <em>失败记录</em>
          </article>
        </section>

        <section className="panel controls-panel" id="mock-flow">
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

        <section className="panel state-panel" id="session">
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

        {!session.token && (
          <section className="panel login-panel auth-entry-panel">
            <div>
              <h2>登录或注册后继续测试</h2>
              <p>
                认证页面已独立拆分。注册时可选择账户用途，但不会自助授予管理员权限。
              </p>
            </div>
            <a className="auth-entry-action" href="/login">
              进入登录 / 注册
            </a>
          </section>
        )}

        {session.token && (
          <section className="panel password-panel" id="security">
            <div className="panel-heading">
              <div>
                <h2>账户安全</h2>
                <p className="panel-note">修改成功后所有旧登录令牌立即失效</p>
              </div>
              <button onClick={clearSession} disabled={busy}>
                退出登录
              </button>
            </div>
            <div className="password-form">
              <label>
                当前密码
                <input
                  type="password"
                  autoComplete="current-password"
                  value={passwordChange.currentPassword}
                  onChange={(event) => setPasswordChange({
                    ...passwordChange,
                    currentPassword: event.target.value,
                  })}
                />
              </label>
              <label>
                新密码
                <input
                  type="password"
                  autoComplete="new-password"
                  value={passwordChange.newPassword}
                  onChange={(event) => setPasswordChange({
                    ...passwordChange,
                    newPassword: event.target.value,
                  })}
                  placeholder="至少 16 个字符"
                />
              </label>
              <label>
                确认新密码
                <input
                  type="password"
                  autoComplete="new-password"
                  value={passwordChange.confirmPassword}
                  onChange={(event) => setPasswordChange({
                    ...passwordChange,
                    confirmPassword: event.target.value,
                  })}
                />
              </label>
              <button
                onClick={changeOwnPassword}
                disabled={
                  busy ||
                  !passwordChange.currentPassword ||
                  !passwordChange.newPassword ||
                  !passwordChange.confirmPassword
                }
              >
                修改密码
              </button>
            </div>
          </section>
        )}

        {session.token && (
          <section className="panel testnet-panel" id="exchange-accounts">
            <div className="panel-heading">
              <div>
                <h2>交易所只读账户</h2>
                <p className="panel-note">
                  支持测试网及 OKX 正式 API 只读认证；交易开关固定关闭，API Key 必须关闭提现权限
                </p>
              </div>
              <span className={testnetKeyConfigured ? "mfa-enabled" : "mfa-disabled"}>
                {testnetKeyConfigured ? "密钥已配置" : "未确认密钥"}
              </span>
            </div>

            <div className="testnet-account-row">
              <label>
                已有只读账户
                <select
                  value={testnetAccountId}
                  onChange={(event) => void selectTestnetAccount(event.target.value)}
                  disabled={busy}
                >
                  <option value="">请选择</option>
                  {testnetAccounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.account_label} · {account.exchange_name.toUpperCase()} · {account.account_mode}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                API 环境
                <select
                  value={testnetForm.accountMode}
                  onChange={(event) => setTestnetForm({
                    ...testnetForm,
                    accountMode: event.target.value as "TESTNET" | "REAL",
                    exchangeName:
                      event.target.value === "REAL" ? "okx" : testnetForm.exchangeName,
                  })}
                  disabled={busy || Boolean(selectedTestnetAccount)}
                >
                  <option value="TESTNET">测试网 / Demo</option>
                  <option value="REAL">OKX Production（仅只读）</option>
                </select>
              </label>
              <label>
                交易所
                <select
                  value={testnetForm.exchangeName}
                  onChange={(event) => setTestnetForm({
                    ...testnetForm,
                    exchangeName: event.target.value as "binance" | "bybit" | "okx",
                  })}
                  disabled={
                    busy ||
                    Boolean(selectedTestnetAccount) ||
                    testnetForm.accountMode === "REAL"
                  }
                >
                  <option value="binance">Binance Testnet</option>
                  <option value="bybit">Bybit Testnet</option>
                  <option value="okx">OKX Demo Trading</option>
                </select>
              </label>
              <label>
                账户标签
                <input
                  value={testnetForm.accountLabel}
                  onChange={(event) => setTestnetForm({
                    ...testnetForm,
                    accountLabel: event.target.value,
                  })}
                  placeholder="例如 Binance Testnet"
                  disabled={busy}
                />
              </label>
              <button onClick={createTestnetAccount} disabled={busy}>
                创建账户
              </button>
            </div>

            <div className="testnet-credential-row">
              <label>
                API Key
                <input
                  type="password"
                  autoComplete="off"
                  value={testnetForm.apiKey}
                  onChange={(event) => setTestnetForm({
                    ...testnetForm,
                    apiKey: event.target.value,
                  })}
                  disabled={busy || !testnetAccountId}
                />
              </label>
              <label>
                API Secret
                <input
                  type="password"
                  autoComplete="new-password"
                  value={testnetForm.apiSecret}
                  onChange={(event) => setTestnetForm({
                    ...testnetForm,
                    apiSecret: event.target.value,
                  })}
                  disabled={busy || !testnetAccountId}
                />
              </label>
              <label>
                Passphrase {testnetForm.exchangeName === "okx" ? "（必填）" : "（可选）"}
                <input
                  type="password"
                  autoComplete="new-password"
                  value={testnetForm.passphrase}
                  onChange={(event) => setTestnetForm({
                    ...testnetForm,
                    passphrase: event.target.value,
                  })}
                  disabled={busy || !testnetAccountId}
                />
              </label>
            </div>

            <div className="testnet-action-row">
              <label>
                当前登录密码
                <input
                  type="password"
                  autoComplete="current-password"
                  value={testnetForm.password}
                  onChange={(event) => setTestnetForm({
                    ...testnetForm,
                    password: event.target.value,
                  })}
                  disabled={busy || !testnetAccountId}
                />
              </label>
              <button
                onClick={saveTestnetCredentials}
                disabled={
                  busy ||
                  !testnetAccountId ||
                  !testnetForm.apiKey ||
                  !testnetForm.apiSecret ||
                  !testnetForm.password
                }
              >
                加密保存密钥
              </button>
              <button
                className="primary-action testnet-check-action"
                onClick={runTestnetReadOnlyCheck}
                disabled={
                  busy ||
                  !testnetAccountId ||
                  !testnetKeyConfigured ||
                  !testnetForm.password
                }
              >
                执行只读认证
              </button>
            </div>

            {selectedTestnetAccount?.account_mode === "REAL" && (
              <div className="testnet-admission-panel">
                <div className="testnet-admission-heading">
                  <div>
                    <h3>Phase 4 REAL readiness</h3>
                    <p>
                      Read-only internal gate. Checks super admin, MFA, REAL OKX,
                      disabled trading flags, risk settings, and encrypted key
                      metadata. It does not call the exchange or submit orders.
                    </p>
                  </div>
                  <button
                    onClick={runPhase4ReadinessCheck}
                    disabled={busy || !testnetAccountId}
                  >
                    Read-only check
                  </button>
                </div>

                {phase4ReadinessReport ? (
                  <>
                    <div className="testnet-admission-summary">
                      <span
                        className={
                          phase4ReadinessReport.overall_status === "PASS"
                            ? "mfa-enabled"
                            : "mfa-disabled"
                        }
                      >
                        {phase4ReadinessReport.overall_status}
                      </span>
                      <span>{phase4PassedCount} PASS</span>
                      <span>{phase4BlockedCount} BLOCKED</span>
                      <span>
                        order_submission_authorized=
                        {String(phase4ReadinessReport.order_submission_authorized)}
                      </span>
                    </div>
                    <div className="testnet-admission-checks">
                      {phase4ReadinessReport.checks.map((check) => (
                        <div key={check.name} className="testnet-admission-check">
                          <strong>{check.name}</strong>
                          <span
                            className={
                              check.status === "PASS"
                                ? "mfa-enabled"
                                : "mfa-disabled"
                            }
                          >
                            {check.status}
                          </span>
                          <p>{check.detail}</p>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="empty-admission">
                    Select a REAL OKX account and run the read-only readiness
                    gate before any Phase 4 proposal.
                  </p>
                )}
              </div>
            )}

            <div className="testnet-admission-panel">
              <div className="testnet-admission-heading">
                <div>
                  <h3>TESTNET 下单准入自检</h3>
                  <p>仅读取账户、风控和运行开关状态；不启用交易，不提交订单。</p>
                </div>
                <button
                  onClick={runTestnetOrderAdmissionCheck}
                  disabled={
                    busy ||
                    !testnetAccountId ||
                    selectedTestnetAccount?.account_mode !== "TESTNET"
                  }
                >
                  只读自检
                </button>
              </div>

              {testnetAdmissionReport ? (
                <>
                  <div className="testnet-admission-summary">
                    <span
                      className={
                        testnetAdmissionReport.overall_status === "PASS"
                          ? "mfa-enabled"
                          : "mfa-disabled"
                      }
                    >
                      {testnetAdmissionReport.overall_status}
                    </span>
                    <span>read_only={String(testnetAdmissionReport.read_only)}</span>
                    <span>
                      order_submission_authorized=
                      {String(testnetAdmissionReport.order_submission_authorized)}
                    </span>
                  </div>
                  <div className="testnet-admission-checks">
                    {testnetAdmissionReport.checks.map((check) => (
                      <div key={check.name} className="testnet-admission-check">
                        <strong>{check.name}</strong>
                        <span
                          className={
                            check.status === "PASS" ? "mfa-enabled" : "mfa-disabled"
                          }
                        >
                          {check.status}
                        </span>
                        <p>{check.detail}</p>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="empty-admission">
                  选择 TESTNET 账户后运行自检，结果只用于进入下单窗口前的人工确认。
                </p>
              )}
            </div>

            <div className="testnet-window-plan-panel" id="testnet-window">
              <div className="testnet-admission-heading">
                <div>
                  <h3>TESTNET 下单窗口计划</h3>
                  <p>
                    只读准备视图。加载计划不会启用 adapter、不会修改交易开关、不会写入审批、不会提交订单。
                  </p>
                </div>
                <button
                  onClick={runTestnetOrderWindowPlan}
                  disabled={
                    busy ||
                    !testnetAccountId ||
                    selectedTestnetAccount?.account_mode !== "TESTNET"
                  }
                >
                  加载窗口计划
                </button>
              </div>

              {testnetOrderWindowPlan ? (
                <>
                  <div className="testnet-window-dashboard">
                    <div className="testnet-window-ticket">
                      <div className="testnet-window-ticket-header">
                        <div>
                          <span>Order Window</span>
                          <strong>
                            {testnetWindowApprovalForm.symbol.trim().toUpperCase() || "-"}
                          </strong>
                        </div>
                        <span
                          className={
                            testnetWindowReady ? "mfa-enabled" : "mfa-disabled"
                          }
                        >
                          {testnetWindowReady ? "READY" : "BLOCKED"}
                        </span>
                      </div>
                      <div className="testnet-window-ticket-grid">
                        {testnetOrderWindowPreview.map((item) => (
                          <div key={item.label}>
                            <span>{item.label}</span>
                            <strong>{item.value}</strong>
                          </div>
                        ))}
                      </div>
                      <div className="testnet-window-ticket-note">
                        此窗口只记录审批审计，当前版本不会发送测试网或真实订单。
                      </div>
                    </div>

                    <div className="testnet-window-status-rail">
                      <div>
                        <span>只读认证</span>
                        <strong>
                          {testnetKeyConfigured ? "已配置密钥" : "未配置密钥"}
                        </strong>
                      </div>
                      <div>
                        <span>准入检查</span>
                        <strong>
                          {testnetAdmissionReport
                            ? `${admissionPassedCount} PASS / ` +
                              `${admissionBlockedCount} BLOCKED`
                            : "未执行"}
                        </strong>
                      </div>
                      <div>
                        <span>窗口计划</span>
                        <strong>{testnetOrderWindowPlan.status}</strong>
                      </div>
                      <div>
                        <span>最近审批</span>
                        <strong>
                          {lastTestnetApproval
                            ? testnetApprovalRemainingLabel
                            : "未记录"}
                        </strong>
                      </div>
                    </div>
                  </div>

                  {testnetAdmissionReport && (
                    <div className="risk-visual-grid">
                      {testnetAdmissionReport.checks.map((check) => (
                        <div
                          key={check.name}
                          className={`risk-visual-card ${
                            check.status === "PASS" ? "risk-pass" : "risk-blocked"
                          }`}
                        >
                          <span>{check.required ? "必需" : "可选"}</span>
                          <strong>{check.name}</strong>
                          <p>{check.detail}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="testnet-admission-summary">
                    <span
                      className={
                        testnetOrderWindowPlan.status === "READY_FOR_SEPARATE_APPROVAL"
                          ? "mfa-enabled"
                          : "mfa-disabled"
                      }
                    >
                      {testnetOrderWindowPlan.status}
                    </span>
                    <span>
                      mutations_allowed=
                      {String(testnetOrderWindowPlan.mutations_allowed)}
                    </span>
                    <span>
                      order_submission_authorized=
                      {String(testnetOrderWindowPlan.order_submission_authorized)}
                    </span>
                  </div>
                  <div className="testnet-window-state">
                    {Object.entries(testnetOrderWindowPlan.state).map(([key, value]) => (
                      <div key={key}>
                        <strong>{key}</strong>
                        <span>{String(value)}</span>
                      </div>
                    ))}
                  </div>
                  {testnetOrderWindowPlan.blocked_reasons.length > 0 && (
                    <div className="testnet-window-list">
                      <strong>阻断原因</strong>
                      <ol>
                        {testnetOrderWindowPlan.blocked_reasons.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ol>
                    </div>
                  )}
                  <div className="testnet-window-list">
                    <strong>人工操作前置步骤</strong>
                    <ol>
                      {testnetOrderWindowPlan.required_operator_steps.map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  </div>
                  <div className="testnet-window-approval">
                    <strong>仅记录审批审计</strong>
                    <p>
                      写入 append-only 审计记录；不会开启交易开关、不会启用 adapter、不会提交订单。
                    </p>
                    <div className="testnet-window-guardrail">
                      <strong>安全边界</strong>
                      <span>
                        按钮只调用审批审计接口，不调用 place_order，不改变 trading_enabled。
                      </span>
                    </div>
                    <div className="testnet-window-approval-grid">
                      <label>
                        Symbol
                        <input
                          value={testnetWindowApprovalForm.symbol}
                          onChange={(event) => setTestnetWindowApprovalForm({
                            ...testnetWindowApprovalForm,
                            symbol: event.target.value,
                          })}
                        />
                      </label>
                      <label>
                        Side
                        <select
                          value={testnetWindowApprovalForm.side}
                          onChange={(event) => setTestnetWindowApprovalForm({
                            ...testnetWindowApprovalForm,
                            side: event.target.value as "BUY" | "SELL",
                          })}
                        >
                          <option value="BUY">BUY</option>
                          <option value="SELL">SELL</option>
                        </select>
                      </label>
                      <label>
                        Max quantity
                        <input
                          value={testnetWindowApprovalForm.maxQuantity}
                          onChange={(event) => setTestnetWindowApprovalForm({
                            ...testnetWindowApprovalForm,
                            maxQuantity: event.target.value,
                          })}
                        />
                      </label>
                      <label>
                        Max notional
                        <input
                          value={testnetWindowApprovalForm.maxNotional}
                          onChange={(event) => setTestnetWindowApprovalForm({
                            ...testnetWindowApprovalForm,
                            maxNotional: event.target.value,
                          })}
                        />
                      </label>
                      <label>
                        Duration minutes
                        <input
                          value={testnetWindowApprovalForm.durationMinutes}
                          onChange={(event) => setTestnetWindowApprovalForm({
                            ...testnetWindowApprovalForm,
                            durationMinutes: event.target.value,
                          })}
                        />
                      </label>
                    </div>
                    <button
                      onClick={recordTestnetOrderWindowApproval}
                      disabled={
                        busy ||
                        !["super_admin", "admin"].includes(session.role) ||
                        testnetOrderWindowPlan.status !== "READY_FOR_SEPARATE_APPROVAL"
                      }
                    >
                      记录审批审计
                    </button>
                    {lastTestnetApproval && (
                      <div className="testnet-approval-record">
                        <div>
                          <span>Audit Log ID</span>
                          <strong>{lastTestnetApproval.audit_log_id}</strong>
                        </div>
                        <div>
                          <span>窗口剩余</span>
                          <strong>{testnetApprovalRemainingLabel}</strong>
                        </div>
                        <div>
                          <span>预计结束</span>
                          <strong>{testnetApprovalExpiresAtLabel}</strong>
                        </div>
                        <div>
                          <span>提交授权</span>
                          <strong>
                            {String(lastTestnetApproval.order_submission_authorized)}
                          </strong>
                        </div>
                      </div>
                    )}
                    <div className="testnet-submit-box">
                      <div className="testnet-submit-heading">
                        <div>
                          <strong>TESTNET LIMIT order submit</strong>
                          <p>
                            Uses the backend testnet gate, recent audit approval,
                            rate limit service, and signed exchange adapter. REAL
                            accounts are not accepted here.
                          </p>
                        </div>
                        <span className={canSubmitTestnetOrder ? "mfa-enabled" : "mfa-disabled"}>
                          {canSubmitTestnetOrder ? "WINDOW ACTIVE" : "LOCKED"}
                        </span>
                      </div>
                      <div className="testnet-window-guardrail">
                        <strong>Submit guard</strong>
                        <span>
                          Backend must find a matching non-expired approval audit
                          log for symbol, side, quantity, and notional before any
                          exchange request is sent.
                        </span>
                      </div>
                      <div className="testnet-window-approval-grid">
                        <label>
                          Symbol
                          <input
                            value={testnetOrderSubmitForm.symbol}
                            onChange={(event) => setTestnetOrderSubmitForm({
                              ...testnetOrderSubmitForm,
                              symbol: event.target.value,
                            })}
                          />
                        </label>
                        <label>
                          Side
                          <select
                            value={testnetOrderSubmitForm.side}
                            onChange={(event) => setTestnetOrderSubmitForm({
                              ...testnetOrderSubmitForm,
                              side: event.target.value as "BUY" | "SELL",
                            })}
                          >
                            <option value="BUY">BUY</option>
                            <option value="SELL">SELL</option>
                          </select>
                        </label>
                        <label>
                          Quantity
                          <input
                            value={testnetOrderSubmitForm.quantity}
                            onChange={(event) => setTestnetOrderSubmitForm({
                              ...testnetOrderSubmitForm,
                              quantity: event.target.value,
                            })}
                          />
                        </label>
                        <label>
                          Limit price
                          <input
                            value={testnetOrderSubmitForm.price}
                            onChange={(event) => setTestnetOrderSubmitForm({
                              ...testnetOrderSubmitForm,
                              price: event.target.value,
                            })}
                          />
                        </label>
                        <label>
                          Client order ID
                          <input
                            value={testnetOrderSubmitForm.clientOrderId}
                            onChange={(event) => setTestnetOrderSubmitForm({
                              ...testnetOrderSubmitForm,
                              clientOrderId: event.target.value,
                            })}
                            placeholder="auto if empty"
                          />
                        </label>
                      </div>
                      <button
                        className="testnet-submit-action"
                        onClick={submitTestnetOrder}
                        disabled={busy || !canSubmitTestnetOrder}
                      >
                        Submit TESTNET LIMIT order
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <p className="empty-admission">
                  选择 TESTNET 账户并加载窗口计划后，才能进入单独批准的测试网下单窗口。
                </p>
              )}
            </div>
          </section>
        )}

        {session.role === "super_admin" && (
          <section className="panel mfa-panel">
            <div className="panel-heading">
              <div>
                <h2>多因素认证</h2>
                <p className="panel-note">
                  {mfaStatus.enabled
                    ? "TOTP MFA 已启用"
                    : "敏感管理操作启用前必须配置 MFA"}
                </p>
              </div>
              <span className={mfaStatus.enabled ? "mfa-enabled" : "mfa-disabled"}>
                {mfaStatus.enabled ? "已启用" : "未启用"}
              </span>
            </div>

            {!mfaStatus.enabled && mfaEnrollment.recoveryCodes.length === 0 && (
              <>
                <div className="mfa-start">
                  <label>
                    当前密码
                    <input
                      type="password"
                      autoComplete="current-password"
                      value={mfaForm.password}
                      onChange={(event) => setMfaForm({
                        ...mfaForm,
                        password: event.target.value,
                      })}
                    />
                  </label>
                  <button
                    onClick={startMfaEnrollment}
                    disabled={busy || !mfaForm.password}
                  >
                    {mfaStatus.enrollmentPending ? "重新生成密钥" : "开始配置"}
                  </button>
                </div>

                {mfaStatus.enrollmentPending &&
                  !mfaEnrollment.manualEntryKey && (
                    <p className="mfa-warning">
                      上次配置尚未确认。重新生成密钥后再继续。
                    </p>
                  )}

                {mfaEnrollment.manualEntryKey && (
                  <div className="mfa-setup">
                    <img
                      className="mfa-qr"
                      src={mfaEnrollment.qrDataUrl}
                      alt="TOTP MFA 配置二维码"
                    />
                    <div className="mfa-confirm">
                      <div>
                        <strong>在认证器中扫描二维码</strong>
                        <p>也可手工输入下方密钥。密钥仅在当前页面显示。</p>
                        <code>{mfaEnrollment.manualEntryKey}</code>
                      </div>
                      <label>
                        6 位验证码
                        <input
                          inputMode="numeric"
                          autoComplete="one-time-code"
                          maxLength={6}
                          value={mfaForm.code}
                          onChange={(event) => setMfaForm({
                            ...mfaForm,
                            code: event.target.value.replace(/\D/g, ""),
                          })}
                          placeholder="000000"
                        />
                      </label>
                      <button
                        onClick={confirmMfaEnrollment}
                        disabled={busy || mfaForm.code.length !== 6}
                      >
                        确认并启用
                      </button>
                    </div>
                  </div>
                )}
              </>
            )}

            {mfaStatus.enabled && (
              <div className="mfa-start">
                <label>
                  当前密码
                  <input
                    type="password"
                    autoComplete="current-password"
                    value={mfaForm.password}
                    onChange={(event) => setMfaForm({
                      ...mfaForm,
                      password: event.target.value,
                    })}
                  />
                </label>
                <label>
                  MFA 验证码或恢复码
                  <input
                    autoComplete="one-time-code"
                    value={mfaForm.code}
                    onChange={(event) => setMfaForm({
                      ...mfaForm,
                      code: event.target.value,
                    })}
                    placeholder="关闭 MFA 时填写"
                  />
                </label>
                <button
                  className="danger-action"
                  onClick={disableMfa}
                  disabled={busy || !mfaForm.password || mfaForm.code.length < 6}
                >
                  关闭 MFA
                </button>
              </div>
            )}

            {mfaEnrollment.recoveryCodes.length > 0 && (
              <div className="recovery-section">
                <strong>恢复码仅显示一次</strong>
                <p>
                  请离线保存。任何一个恢复码只能使用一次，保存后退出并重新登录。
                </p>
                <div className="recovery-codes">
                  {mfaEnrollment.recoveryCodes.map((code) => (
                    <code key={code}>{code}</code>
                  ))}
                </div>
                <button onClick={clearSession}>
                  已保存恢复码并退出登录
                </button>
              </div>
            )}
          </section>
        )}

        {session.role === "super_admin" && (
          <section className="panel storage-panel" id="storage">
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

        <section className="panel log-panel" id="audit-log">
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
      </div>
    </main>
  );
}
