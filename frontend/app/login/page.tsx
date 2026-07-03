"use client";

import { useMemo, useState } from "react";

type AuthMode = "login" | "register";

type AccountIntent =
  | "normal_user"
  | "copy_observer"
  | "strategy_tester"
  | "team_member";

type AuthLog = {
  ok: boolean;
  message: string;
};

type UserProfile = {
  id: string;
  email: string;
  username: string;
  role: string;
  is_active: boolean;
};

const SESSION_TOKEN_STORAGE_KEY = "trading_platform_token";

const accountIntents: Array<{
  value: AccountIntent;
  title: string;
  text: string;
}> = [
  {
    value: "normal_user",
    title: "普通用户",
    text: "默认权限，用于手动交易、账户配置和基础测试。",
  },
  {
    value: "copy_observer",
    title: "跟单观察",
    text: "注册后仍为普通用户，跟单权限需要管理员授权。",
  },
  {
    value: "strategy_tester",
    title: "策略测试",
    text: "用于测试信号、风控和模拟执行流程。",
  },
  {
    value: "team_member",
    title: "团队成员",
    text: "预留团队场景，注册后需要管理员分配共享权限。",
  },
];

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

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatError(value: unknown) {
  if (value instanceof Error) {
    return value.message;
  }
  return String(value);
}

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>("login");
  const [apiBase] = useState(resolveApiBase);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<AuthLog | null>(null);
  const [showLoginPassword, setShowLoginPassword] = useState(false);
  const [showRegisterPassword, setShowRegisterPassword] = useState(false);
  const [showRegisterConfirmPassword, setShowRegisterConfirmPassword] =
    useState(false);
  const [loginForm, setLoginForm] = useState({
    usernameOrEmail: "",
    password: "",
    mfaCode: "",
  });
  const [registerForm, setRegisterForm] = useState({
    email: "",
    username: "",
    password: "",
    confirmPassword: "",
    intent: "normal_user" as AccountIntent,
  });

  const apiRoot = useMemo(() => `${apiBase}/api/v1`, [apiBase]);
  const selectedIntent = accountIntents.find(
    (intent) => intent.value === registerForm.intent,
  );

  async function apiRequest(
    method: string,
    path: string,
    payload: Record<string, unknown>,
    expectedStatus = 200,
  ) {
    const response = await fetch(`${apiRoot}${path}`, {
      method,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const text = await response.text();
    const body = text ? JSON.parse(text) : null;
    if (response.status !== expectedStatus) {
      const detail = isObject(body) && body.detail ? String(body.detail) : text;
      throw new Error(detail || `${method} ${path} 返回 ${response.status}`);
    }
    return body;
  }

  async function loadProfile(token: string): Promise<UserProfile> {
    const response = await fetch(`${apiRoot}/users/me`, {
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
      },
    });
    const text = await response.text();
    const body = text ? JSON.parse(text) : null;
    if (response.status !== 200 || !isObject(body)) {
      throw new Error("登录成功，但读取用户资料失败");
    }
    const userId = body.id ?? body.user_id;
    if (typeof userId !== "string" || userId.trim() === "") {
      throw new Error("登录成功，但用户资料缺少 user_id");
    }
    return {
      id: userId,
      email: String(body.email),
      username: String(body.username),
      role: String(body.role),
      is_active: Boolean(body.is_active),
    };
  }

  async function login(usernameOrEmail: string, password: string, mfaCode = "") {
    const tokenBody = await apiRequest("POST", "/auth/login", {
      username_or_email: usernameOrEmail,
      password,
      ...(mfaCode ? { mfa_code: mfaCode } : {}),
    });
    if (!isObject(tokenBody) || typeof tokenBody.access_token !== "string") {
      throw new Error("登录返回格式异常");
    }
    const token = tokenBody.access_token;
    const profile = await loadProfile(token);
    window.localStorage.setItem(SESSION_TOKEN_STORAGE_KEY, token);
    setLog({
      ok: true,
      message: `已登录 ${profile.username}，角色 ${profile.role}`,
    });
    window.location.href = "/trade";
  }

  async function submitLogin() {
    setBusy(true);
    setLog(null);
    try {
      await login(
        loginForm.usernameOrEmail,
        loginForm.password,
        loginForm.mfaCode,
      );
    } catch (error) {
      setLog({ ok: false, message: formatError(error) });
    } finally {
      setBusy(false);
    }
  }

  async function submitRegister() {
    setBusy(true);
    setLog(null);
    try {
      if (registerForm.password !== registerForm.confirmPassword) {
        throw new Error("两次输入的新密码不一致");
      }
      await apiRequest(
        "POST",
        "/auth/register",
        {
          email: registerForm.email,
          username: registerForm.username,
          password: registerForm.password,
        },
        201,
      );
      await login(registerForm.username, registerForm.password);
    } catch (error) {
      setLog({ ok: false, message: formatError(error) });
    } finally {
      setBusy(false);
    }
  }

  const canSubmitLogin =
    loginForm.usernameOrEmail.trim() !== "" && loginForm.password !== "";
  const canSubmitRegister =
    registerForm.email.trim() !== "" &&
    registerForm.username.trim() !== "" &&
    registerForm.password.length >= 12 &&
    registerForm.confirmPassword.length >= 12;

  return (
    <main className="auth-page">
      <section className="auth-shell">
        <aside className="auth-market-panel">
          <div className="auth-brand-block">
            <span>模拟优先</span>
            <h1>多租户加密货币交易执行与跟单平台</h1>
            <p>统一账户、统一风控、统一审计。</p>
          </div>

          <div className="market-board" aria-label="登录页安全状态">
            <div>
              <span>BTC/USDT</span>
              <strong>模拟</strong>
              <em>SIM</em>
            </div>
            <div>
              <span>风控引擎</span>
              <strong>开启</strong>
              <em>安全</em>
            </div>
            <div>
              <span>订单模式</span>
              <strong>只读</strong>
              <em>锁定</em>
            </div>
          </div>

          <div className="auth-security-strip">
            <strong>注册不会授予管理员权限</strong>
            <span>管理员、超级管理员和团队授权必须由后台流程授予。</span>
          </div>
        </aside>

        <section className="auth-card">
          <div className="auth-card-heading">
            <div>
              <span>安全认证</span>
              <h2>{mode === "login" ? "登录账户" : "注册账户"}</h2>
            </div>
          </div>

          <div className="auth-tabs" role="tablist" aria-label="认证方式">
            <button
              className={mode === "login" ? "active" : ""}
              onClick={() => setMode("login")}
              type="button"
            >
              登录
            </button>
            <button
              className={mode === "register" ? "active" : ""}
              onClick={() => setMode("register")}
              type="button"
            >
              注册
            </button>
          </div>

          {mode === "login" ? (
            <div className="auth-form">
              <label>
                用户名或邮箱
                <input
                  autoComplete="username"
                  value={loginForm.usernameOrEmail}
                  onChange={(event) =>
                    setLoginForm({
                      ...loginForm,
                      usernameOrEmail: event.target.value,
                    })
                  }
                />
              </label>
              <label>
                密码
                <span className="password-input-wrap">
                  <input
                    autoComplete="current-password"
                    type={showLoginPassword ? "text" : "password"}
                    value={loginForm.password}
                    onChange={(event) =>
                      setLoginForm({
                        ...loginForm,
                        password: event.target.value,
                      })
                    }
                  />
                  <button
                    aria-label={showLoginPassword ? "隐藏密码" : "显示密码"}
                    className="password-visibility-button"
                    onClick={() => setShowLoginPassword(!showLoginPassword)}
                    type="button"
                  >
                    <span
                      aria-hidden="true"
                      className={
                        showLoginPassword
                          ? "password-eye-icon visible"
                          : "password-eye-icon"
                      }
                    />
                  </button>
                </span>
              </label>
              <label>
                MFA 验证码或恢复码
                <input
                  autoComplete="one-time-code"
                  value={loginForm.mfaCode}
                  onChange={(event) =>
                    setLoginForm({ ...loginForm, mfaCode: event.target.value })
                  }
                />
              </label>
              <button
                className="auth-submit"
                disabled={busy || !canSubmitLogin}
                onClick={submitLogin}
                type="button"
              >
                登录
              </button>
            </div>
          ) : (
            <div className="auth-form">
              <div className="auth-two-column">
                <label>
                  邮箱
                  <input
                    autoComplete="email"
                    value={registerForm.email}
                    onChange={(event) =>
                      setRegisterForm({
                        ...registerForm,
                        email: event.target.value,
                      })
                    }
                  />
                </label>
                <label>
                  用户名
                  <input
                    autoComplete="username"
                    value={registerForm.username}
                    onChange={(event) =>
                      setRegisterForm({
                        ...registerForm,
                        username: event.target.value,
                      })
                    }
                  />
                </label>
              </div>

              <div className="auth-two-column">
                <label>
                  密码
                  <span className="password-input-wrap">
                    <input
                      autoComplete="new-password"
                      type={showRegisterPassword ? "text" : "password"}
                      value={registerForm.password}
                      onChange={(event) =>
                        setRegisterForm({
                          ...registerForm,
                          password: event.target.value,
                        })
                      }
                    />
                    <button
                      aria-label={
                        showRegisterPassword ? "隐藏密码" : "显示密码"
                      }
                      className="password-visibility-button"
                      onClick={() =>
                        setShowRegisterPassword(!showRegisterPassword)
                      }
                      type="button"
                    >
                      <span
                        aria-hidden="true"
                        className={
                          showRegisterPassword
                            ? "password-eye-icon visible"
                            : "password-eye-icon"
                        }
                      />
                    </button>
                  </span>
                </label>
                <label>
                  确认密码
                  <span className="password-input-wrap">
                    <input
                      autoComplete="new-password"
                      type={showRegisterConfirmPassword ? "text" : "password"}
                      value={registerForm.confirmPassword}
                      onChange={(event) =>
                        setRegisterForm({
                          ...registerForm,
                          confirmPassword: event.target.value,
                        })
                      }
                    />
                    <button
                      aria-label={
                        showRegisterConfirmPassword ? "隐藏密码" : "显示密码"
                      }
                      className="password-visibility-button"
                      onClick={() =>
                        setShowRegisterConfirmPassword(
                          !showRegisterConfirmPassword,
                        )
                      }
                      type="button"
                    >
                      <span
                        aria-hidden="true"
                        className={
                          showRegisterConfirmPassword
                            ? "password-eye-icon visible"
                            : "password-eye-icon"
                        }
                      />
                    </button>
                  </span>
                </label>
              </div>

              <div className="auth-intent-block">
                <div>
                  <strong>账户用途</strong>
                  <span>{selectedIntent?.text}</span>
                </div>
                <div className="auth-intent-grid">
                  {accountIntents.map((intent) => (
                    <button
                      className={
                        registerForm.intent === intent.value ? "active" : ""
                      }
                      key={intent.value}
                      onClick={() =>
                        setRegisterForm({
                          ...registerForm,
                          intent: intent.value,
                        })
                      }
                      type="button"
                    >
                      <strong>{intent.title}</strong>
                      <span>{intent.text}</span>
                    </button>
                  ))}
                </div>
              </div>

              <button
                className="auth-submit"
                disabled={busy || !canSubmitRegister}
                onClick={submitRegister}
                type="button"
              >
                注册并登录
              </button>
            </div>
          )}

          {log ? (
            <div className={log.ok ? "auth-log ok" : "auth-log error"}>
              {log.message}
            </div>
          ) : null}
        </section>
      </section>
    </main>
  );
}
