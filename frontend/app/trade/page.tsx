"use client";

import { useEffect, useMemo, useState } from "react";

type SessionState = {
  token: string;
  userId: string;
  username: string;
  role: string;
};

type ExchangeAccount = {
  id: string;
  exchange_name: "binance" | "bybit" | "okx" | "mock";
  account_label: string;
  account_mode: "SIMULATION" | "TESTNET" | "REAL";
  trading_enabled: boolean;
  is_active: boolean;
};

type OrderSide = "BUY" | "SELL";

const emptySession: SessionState = {
  token: "",
  userId: "",
  username: "",
  role: "",
};

const apiBaseFallback = "http://192.168.2.42:8000/api/v1";

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

export default function TradeWorkspace() {
  const [apiRoot] = useState(resolveApiBase);
  const [session, setSession] = useState<SessionState>(emptySession);
  const [accounts, setAccounts] = useState<ExchangeAccount[]>([]);
  const [activeExchange, setActiveExchange] = useState<ExchangeAccount["exchange_name"]>("okx");
  const [activeSymbol, setActiveSymbol] = useState("BTC/USDT");
  const [orderSide, setOrderSide] = useState<OrderSide>("BUY");
  const [lastStatus, setLastStatus] = useState("READ ONLY");

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
  const activeAccount = exchangeAccounts[0];
  const marketRows = [
    { price: "68,420.5", amount: "0.184", side: "ask" },
    { price: "68,418.2", amount: "0.076", side: "ask" },
    { price: "68,410.0", amount: "0.214", side: "bid" },
    { price: "68,405.4", amount: "0.092", side: "bid" },
  ];
  const accountMode = activeAccount?.account_mode ?? "UNSELECTED";
  const orderLocked =
    !session.token ||
    accountMode === "REAL" ||
    !activeAccount?.trading_enabled ||
    activeExchange !== "mock";

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
          {(["okx", "binance", "bybit", "mock"] as const).map((exchange) => (
            <button
              className={exchange === activeExchange ? "active" : ""}
              key={exchange}
              onClick={() => setActiveExchange(exchange)}
            >
              {exchange.toUpperCase()}
            </button>
          ))}
          {["BTC/USDT", "ETH/USDT", "SOL/USDT"].map((symbol) => (
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
                <strong>{activeExchange.toUpperCase()} · {activeSymbol}</strong>
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

        <section className="trade-api-grid">
          {(["okx", "binance", "bybit", "mock"] as const).map((exchange) => {
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
              <button className="active">Positions</button>
              <button>Open Orders</button>
              <button>History</button>
              <button>Audit</button>
            </div>
            <div className="trade-empty-table">
              No live position data loaded. Use Console for Mock chain validation.
            </div>
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
