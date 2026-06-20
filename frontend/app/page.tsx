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
    return "瀹屾垚";
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
      throw new Error(`${method} ${path} 杩斿洖 ${response.status}: ${formatDetail(body)}`);
    }
    return body;
  }

  function requireObject(result: ApiResult, label: string) {
    if (result === null || Array.isArray(result)) {
      throw new Error(`${label} 杩斿洖鏍煎紡寮傚父`);
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
    await runStep("鍋ュ悍妫€鏌?, async () => {
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
      "鐢ㄦ埛璧勬枡",
    );
    const role = String(profile.role);
    let locations: StorageLocation[] = [];
    let nextMfaStatus: MfaStatus = {
      enabled: false,
      enrollmentPending: false,
    };

    if (role === "super_admin") {
      const result = await apiRequest(
        "GET",
        "/admin/storage/locations",
        undefined,
        token,
      );
      if (!Array.isArray(result)) {
        throw new Error("瀛樺偍浣嶇疆杩斿洖鏍煎紡寮傚父");
      }
      locations = result as StorageLocation[];

      const mfaResult = requireObject(
        await apiRequest("GET", "/users/me/mfa", undefined, token),
        "MFA 鐘舵€?,
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
    setStorageLocations(locations);
    setMfaStatus(nextMfaStatus);
    return profile;
  }

  async function refreshStorageLocations() {
    await runStep("鍒锋柊瀛樺偍浣嶇疆", async () => {
      const result = await apiRequest("GET", "/admin/storage/locations");
      if (!Array.isArray(result)) {
        throw new Error("瀛樺偍浣嶇疆杩斿洖鏍煎紡寮傚父");
      }
      const locations = result as StorageLocation[];
      setStorageLocations(locations);
      return locations;
    });
  }

  async function registerAndLogin() {
    await runStep("娉ㄥ唽骞剁櫥褰曟祴璇曠敤鎴?, async () => {
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
        "娉ㄥ唽",
      );
      const tokenResponse = requireObject(
        await apiRequest(
          "POST",
          "/auth/login",
          { username_or_email: username, password },
          "",
        ),
        "鐧诲綍",
      );
      const profile = await loadAuthenticatedSession(
        String(tokenResponse.access_token),
      );
      return { user_id: profile.id, username: profile.username };
    });
  }

  async function loginExisting() {
    await runStep("鐧诲綍宸叉湁鐢ㄦ埛", async () => {
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
        "鐧诲綍",
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
  }

  async function startMfaEnrollment() {
    await runStep("寮€濮?MFA 閰嶇疆", async () => {
      const reauthentication = requireObject(
        await apiRequest("POST", "/auth/reauthenticate", {
          password: mfaForm.password,
        }),
        "瀵嗙爜鍐嶈璇?,
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
        "MFA 娉ㄥ唽",
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
    await runStep("鍚敤 MFA", async () => {
      const reauthentication = requireObject(
        await apiRequest("POST", "/auth/reauthenticate", {
          password: mfaForm.password,
        }),
        "瀵嗙爜鍐嶈璇?,
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
        "MFA 纭",
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
    await runStep("鍏抽棴 MFA", async () => {
      const reauthentication = requireObject(
        await apiRequest("POST", "/auth/reauthenticate", {
          password: mfaForm.password,
        }),
        "瀵嗙爜鍐嶈璇?,
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
      appendLog("淇敼瀵嗙爜", false, "涓ゆ杈撳叆鐨勬柊瀵嗙爜涓嶄竴鑷?);
      return;
    }
    if (passwordChange.newPassword.length < 16) {
      appendLog("淇敼瀵嗙爜", false, "鏂板瘑鐮佽嚦灏戦渶瑕?16 涓瓧绗?);
      return;
    }
    await runStep("淇敼瀵嗙爜", async () => {
      const result = await apiRequest("POST", "/users/me/password", {
        current_password: passwordChange.currentPassword,
        new_password: passwordChange.newPassword,
      });
      clearSession();
      return { result, session_cleared: true, login_required: true };
    });
  }

  async function createMockAccount() {
    await runStep("鍒涘缓 Mock 妯℃嫙璐︽埛", async () => {
      const account = requireObject(
        await apiRequest("POST", "/exchange-accounts", {
          exchange_name: "mock",
          account_label: "UI Mock Simulation",
          account_mode: "SIMULATION",
          trading_enabled: true,
        }),
        "鍒涘缓璐︽埛",
      );
      const accountId = String(account.id);
      setSession((current) => ({ ...current, accountId }));
      return { account_id: accountId, mode: account.account_mode };
    });
  }

  async function configureMockKey() {
    await runStep("鍐欏叆妯℃嫙 API Key 鍏冩暟鎹?, async () => {
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
    await runStep("寮€鍚ā鎷熼鎺т氦鏄?, async () => {
      return apiRequest("PATCH", `/risk-settings/${session.accountId}`, {
        trading_enabled: true,
        min_order_quantity: "0.01",
        max_order_quantity: "1",
        max_single_order_notional: "1000",
      });
    });
  }

  async function previewTarget() {
    await runStep("浠撲綅宸棰勮", async () => {
      return apiRequest(
        "POST",
        `/positions/${session.accountId}/target-preview?symbol=BTCUSDT&target_quantity=0.5`,
      );
    });
  }

  async function executeManualOrder() {
    await runStep("鎵ц鎵嬪伐 Mock 璁㈠崟", async () => {
      const signal = requireObject(
        await apiRequest(
          "POST",
          "/signals/manual",
          { symbol: "BTCUSDT", side: "BUY", order_type: "MARKET", quantity: "0.2" },
          session.token,
          201,
        ),
        "鍒涘缓淇″彿",
      );
      const execution = requireObject(
        await apiRequest("POST", `/orders/execute-signal/${signal.id}`, {
          exchange_account_id: session.accountId,
        }),
        "鎵ц璁㈠崟",
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
    await runStep("骞傜瓑閲嶅鎵ц鏍￠獙", async () => {
      const duplicate = requireObject(
        await apiRequest("POST", `/orders/execute-signal/${session.signalId}`, {
          exchange_account_id: session.accountId,
        }),
        "閲嶅鎵ц",
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
          <div className="brand">澶氱鎴峰姞瀵嗚揣甯佷氦鏄撴墽琛屼笌璺熷崟骞冲彴</div>
          <div className="subtle">Ubuntu 闆嗘垚娴嬭瘯鎺у埗鍙?/div>
        </div>
        <div className="status">SIMULATION ONLY</div>
      </header>

      <div className="main console-layout">
        <section className="panel hero-panel">
          <div>
            <h1>寮€鍙戠幆澧冩搷浣滃彴</h1>
            <p>
              褰撳墠椤甸潰鍙蛋 MockExchange 涓?SIMULATION 妯″紡锛岀敤浜庨獙璇佺櫥褰曘€佺鎴烽殧绂汇€侀鎺с€佷粨浣嶅樊棰濄€佽鍗曠姸鎬佹満鍜屽箓绛夋墽琛屻€?            </p>
          </div>
          <div className="api-chip">API {apiRoot}</div>
        </section>

        <section className="panel controls-panel">
          <div className="panel-heading">
            <h2>蹇€熸祦绋?/h2>
            <span>涓嶄細鍙戦€佺湡瀹炰氦鏄撴墍璁㈠崟</span>
          </div>
          <div className="button-grid">
            <button onClick={checkHealth} disabled={busy}>鍋ュ悍妫€鏌?/button>
            <button onClick={registerAndLogin} disabled={busy}>娉ㄥ唽娴嬭瘯鐢ㄦ埛</button>
            <button onClick={createMockAccount} disabled={busy || !session.token}>鍒涘缓 Mock 璐︽埛</button>
            <button onClick={configureMockKey} disabled={busy || !canUseAccount}>閰嶇疆妯℃嫙 Key</button>
            <button onClick={enableRisk} disabled={busy || !canUseAccount}>寮€鍚鎺т氦鏄?/button>
            <button onClick={previewTarget} disabled={busy || !canUseAccount}>浠撲綅棰勮</button>
            <button onClick={executeManualOrder} disabled={busy || !canUseAccount}>鎵ц璁㈠崟</button>
            <button onClick={verifyIdempotency} disabled={busy || !canVerifyIdempotency}>骞傜瓑鏍￠獙</button>
          </div>
          <button className="primary-action" onClick={runFullMockFlow} disabled={busy}>
            涓€閿繍琛?Mock 鍏ㄩ摼璺?          </button>
        </section>

        <section className="panel state-panel">
          <div className="panel-heading">
            <h2>浼氳瘽鐘舵€?/h2>
            <span>{busy ? "杩愯涓? : "寰呭懡"}</span>
          </div>
          <dl className="state-list">
            <div><dt>鐢ㄦ埛</dt><dd>{session.username || "鏈櫥褰?}</dd></div>
            <div><dt>User ID</dt><dd>{session.userId || "-"}</dd></div>
            <div><dt>瑙掕壊</dt><dd>{session.role || "-"}</dd></div>
            <div><dt>璐︽埛 ID</dt><dd>{session.accountId || "-"}</dd></div>
            <div><dt>鏈€杩戜俊鍙?/dt><dd>{session.signalId || "-"}</dd></div>
            <div><dt>鏈€杩戞墽琛?/dt><dd>{session.executionId || "-"}</dd></div>
          </dl>
        </section>

        <section className="panel login-panel">
          <div className="panel-heading">
            <h2>宸叉湁鐢ㄦ埛鐧诲綍</h2>
            <span>鍙€?/span>
          </div>
          <div className="form-row">
            <label>
              鐢ㄦ埛鍚嶆垨閭
              <input
                value={manualLogin.usernameOrEmail}
                onChange={(event) => setManualLogin({ ...manualLogin, usernameOrEmail: event.target.value })}
                placeholder="username@example.com"
              />
            </label>
            <label>
              瀵嗙爜
              <input
                type="password"
                value={manualLogin.password}
                onChange={(event) => setManualLogin({ ...manualLogin, password: event.target.value })}
                placeholder="password"
              />
            </label>
            <label>
              MFA 楠岃瘉鐮佹垨鎭㈠鐮?              <input
                value={manualLogin.mfaCode}
                onChange={(event) => setManualLogin({
                  ...manualLogin,
                  mfaCode: event.target.value,
                })}
                placeholder="鍚敤 MFA 鍚庡～鍐?
                autoComplete="one-time-code"
              />
            </label>
            <button onClick={loginExisting} disabled={busy || !manualLogin.usernameOrEmail || !manualLogin.password}>
              鐧诲綍
            </button>
          </div>
        </section>

        {session.token && (
          <section className="panel password-panel">
            <div className="panel-heading">
              <div>
                <h2>璐︽埛瀹夊叏</h2>
                <p className="panel-note">淇敼鎴愬姛鍚庢墍鏈夋棫鐧诲綍浠ょ墝绔嬪嵆澶辨晥</p>
              </div>
              <button onClick={clearSession} disabled={busy}>
                閫€鍑虹櫥褰?              </button>
            </div>
            <div className="password-form">
              <label>
                褰撳墠瀵嗙爜
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
                鏂板瘑鐮?                <input
                  type="password"
                  autoComplete="new-password"
                  value={passwordChange.newPassword}
                  onChange={(event) => setPasswordChange({
                    ...passwordChange,
                    newPassword: event.target.value,
                  })}
                  placeholder="鑷冲皯 16 涓瓧绗?
                />
              </label>
              <label>
                纭鏂板瘑鐮?                <input
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
                淇敼瀵嗙爜
              </button>
            </div>
          </section>
        )}

        {session.role === "super_admin" && (
          <section className="panel mfa-panel">
            <div className="panel-heading">
              <div>
                <h2>澶氬洜绱犺璇?/h2>
                <p className="panel-note">
                  {mfaStatus.enabled
                    ? "TOTP MFA 宸插惎鐢?
                    : "鏁忔劅绠＄悊鎿嶄綔鍚敤鍓嶅繀椤婚厤缃?MFA"}
                </p>
              </div>
              <span className={mfaStatus.enabled ? "mfa-enabled" : "mfa-disabled"}>
                {mfaStatus.enabled ? "宸插惎鐢? : "鏈惎鐢?}
              </span>
            </div>

            {!mfaStatus.enabled && mfaEnrollment.recoveryCodes.length === 0 && (
              <>
                <div className="mfa-start">
                  <label>
                    褰撳墠瀵嗙爜
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
                    {mfaStatus.enrollmentPending ? "閲嶆柊鐢熸垚瀵嗛挜" : "寮€濮嬮厤缃?}
                  </button>
                </div>

                {mfaStatus.enrollmentPending &&
                  !mfaEnrollment.manualEntryKey && (
                    <p className="mfa-warning">
                      涓婃閰嶇疆灏氭湭纭銆傞噸鏂扮敓鎴愬瘑閽ュ悗鍐嶇户缁€?                    </p>
                  )}

                {mfaEnrollment.manualEntryKey && (
                  <div className="mfa-setup">
                    <img
                      className="mfa-qr"
                      src={mfaEnrollment.qrDataUrl}
                      alt="TOTP MFA 閰嶇疆浜岀淮鐮?
                    />
                    <div className="mfa-confirm">
                      <div>
                        <strong>鍦ㄨ璇佸櫒涓壂鎻忎簩缁寸爜</strong>
                        <p>涔熷彲鎵嬪伐杈撳叆涓嬫柟瀵嗛挜銆傚瘑閽ヤ粎鍦ㄥ綋鍓嶉〉闈㈡樉绀恒€?/p>
                        <code>{mfaEnrollment.manualEntryKey}</code>
                      </div>
                      <label>
                        6 浣嶉獙璇佺爜
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
                        纭骞跺惎鐢?                      </button>
                    </div>
                  </div>
                )}
              </>
            )}

            {mfaStatus.enabled && (
              <div className="mfa-start">
                <label>
                  褰撳墠瀵嗙爜
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
                  MFA 楠岃瘉鐮佹垨鎭㈠鐮?                  <input
                    autoComplete="one-time-code"
                    value={mfaForm.code}
                    onChange={(event) => setMfaForm({
                      ...mfaForm,
                      code: event.target.value,
                    })}
                    placeholder="鍏抽棴 MFA 鏃跺～鍐?
                  />
                </label>
                <button
                  className="danger-action"
                  onClick={disableMfa}
                  disabled={busy || !mfaForm.password || mfaForm.code.length < 6}
                >
                  鍏抽棴 MFA
                </button>
              </div>
            )}

            {mfaEnrollment.recoveryCodes.length > 0 && (
              <div className="recovery-section">
                <strong>鎭㈠鐮佷粎鏄剧ず涓€娆?/strong>
                <p>
                  璇风绾夸繚瀛樸€備换浣曚竴涓仮澶嶇爜鍙兘浣跨敤涓€娆★紝淇濆瓨鍚庨€€鍑哄苟閲嶆柊鐧诲綍銆?                </p>
                <div className="recovery-codes">
                  {mfaEnrollment.recoveryCodes.map((code) => (
                    <code key={code}>{code}</code>
                  ))}
                </div>
                <button onClick={clearSession}>
                  宸蹭繚瀛樻仮澶嶇爜骞堕€€鍑虹櫥褰?                </button>
              </div>
            )}
          </section>
        )}

        {session.role === "super_admin" && (
          <section className="panel storage-panel">
            <div className="panel-heading">
              <div>
                <h2>瀛樺偍浣嶇疆</h2>
                <p className="panel-note">鏈嶅姟鍣ㄩ娉ㄥ唽鐧藉悕鍗曪紝鍙鏄剧ず</p>
              </div>
              <button onClick={refreshStorageLocations} disabled={busy}>
                鍒锋柊
              </button>
            </div>
            <div className="storage-list">
              {storageLocations.length === 0 ? (
                <div className="empty-log">鏈厤缃彲鐢ㄥ瓨鍌ㄤ綅缃?/div>
              ) : (
                storageLocations.map((location) => (
                  <div className="storage-row" key={location.id}>
                    <div>
                      <strong>{location.label}</strong>
                      <span>{location.path}</span>
                    </div>
                    <span className={location.is_current ? "current-storage" : "standby-storage"}>
                      {location.is_current ? "褰撳墠閰嶇疆" : "鍙€?}
                    </span>
                  </div>
                ))
              )}
            </div>
          </section>
        )}

        <section className="panel log-panel">
          <div className="panel-heading">
            <h2>鎵ц鏃ュ織</h2>
            <span>{logs.length} 鏉?/span>
          </div>
          <div className="logs">
            {logs.length === 0 ? (
              <div className="empty-log">绛夊緟鎿嶄綔</div>
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
