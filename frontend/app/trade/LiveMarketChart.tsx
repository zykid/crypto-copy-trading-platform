"use client";

import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  createChart,
  type CandlestickData,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";

type ExchangeName = "binance" | "bybit" | "okx" | "mock";
type ChartInterval = "1m" | "5m" | "15m" | "1h";
type ConnectionState = "loading" | "live" | "polling" | "reconnecting" | "error" | "unavailable";

type CandlePayload = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

type Props = {
  apiRoot: string;
  exchange: ExchangeName;
  symbol: string;
  token: string;
  onPriceUpdate?: (price: number | null) => void;
};

const intervalLabels: Record<ChartInterval, string> = {
  "1m": "1 分钟",
  "5m": "5 分钟",
  "15m": "15 分钟",
  "1h": "1 小时",
};

const stateLabels: Record<ConnectionState, string> = {
  loading: "加载历史行情",
  live: "实时",
  polling: "实时轮询",
  reconnecting: "正在重连",
  error: "行情不可用",
  unavailable: "无真实行情",
};

export default function LiveMarketChart({ apiRoot, exchange, symbol, token, onPriceUpdate }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [interval, setIntervalValue] = useState<ChartInterval>("1m");
  const [connectionState, setConnectionState] = useState<ConnectionState>("loading");
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [sourceExchange, setSourceExchange] =
    useState<Exclude<ExchangeName, "mock"> | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const chart = createChart(container, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "#0b1220" },
        textColor: "#94a3b8",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "#182232" },
        horzLines: { color: "#182232" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#243244" },
      timeScale: {
        borderColor: "#243244",
        timeVisible: true,
        secondsVisible: false,
      },
    });
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#20c997",
      downColor: "#ef4444",
      borderUpColor: "#20c997",
      borderDownColor: "#ef4444",
      wickUpColor: "#20c997",
      wickDownColor: "#ef4444",
      priceLineVisible: true,
    });
    seriesRef.current = series;
    return () => {
      seriesRef.current = null;
      chart.remove();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let keepAliveTimer: ReturnType<typeof setInterval> | null = null;
    let pollingTimer: ReturnType<typeof setInterval> | null = null;
    let reconnectAttempt = 0;

    setLastPrice(null);
    setSourceExchange(null);
    onPriceUpdate?.(null);
    setErrorMessage("");
    if (exchange === "mock") {
      seriesRef.current?.setData([]);
      setConnectionState("unavailable");
      return;
    }
    const marketExchange = exchange as Exclude<ExchangeName, "mock">;
    let activeMarketExchange = marketExchange;

    async function fetchCandles(limit: number) {
      const query = new URLSearchParams({ exchange, symbol, interval, limit: String(limit) });
      const response = await fetch(`${apiRoot}/market-data/public/candles?${query.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        cache: "no-store",
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(payload?.detail?.reason ?? `历史行情请求失败 (${response.status})`);
      }
      const candles = Array.isArray(payload?.candles) ? payload.candles : [];
      const payloadSource = payload?.source_exchange;
      const nextSource = isLiveExchange(payloadSource) ? payloadSource : marketExchange;
      return {
        candles: candles.map(toChartCandle).filter(isChartCandle),
        sourceExchange: nextSource,
      };
    }

    async function loadHistory() {
      setConnectionState("loading");
      const history = await fetchCandles(240);
      const chartData = history.candles;
      if (chartData.length === 0) {
        throw new Error("交易所未返回有效 K 线");
      }
      if (cancelled) {
        return;
      }
      seriesRef.current?.setData(chartData);
      activeMarketExchange = history.sourceExchange;
      setSourceExchange(history.sourceExchange);
      seriesRef.current?.priceScale().applyOptions({ autoScale: true });
      const price = chartData[chartData.length - 1].close;
      setLastPrice(price);
      onPriceUpdate?.(activeMarketExchange === marketExchange ? price : null);
      connectSocket(activeMarketExchange);
    }

    async function pollLatestCandle() {
      try {
        const latest = await fetchCandles(20);
        const candle = latest.candles[latest.candles.length - 1];
        if (!candle || cancelled) {
          return;
        }
        seriesRef.current?.update(candle);
        activeMarketExchange = latest.sourceExchange;
        setSourceExchange(latest.sourceExchange);
        setLastPrice(candle.close);
        onPriceUpdate?.(activeMarketExchange === marketExchange ? candle.close : null);
        setConnectionState("polling");
      } catch {
        if (!cancelled) {
          setConnectionState("reconnecting");
        }
      }
    }

    function connectSocket(socketExchange = activeMarketExchange) {
      if (cancelled) {
        return;
      }
      activeMarketExchange = socketExchange;
      socket = new WebSocket(webSocketUrl(socketExchange, symbol, interval));
      socket.onopen = () => {
        reconnectAttempt = 0;
        if (pollingTimer) {
          clearInterval(pollingTimer);
          pollingTimer = null;
        }
        setConnectionState("live");
        const message = subscriptionMessage(socketExchange, symbol, interval);
        if (message && socket?.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify(message));
        }
        if (socketExchange === "okx") {
          keepAliveTimer = setInterval(() => {
            if (socket?.readyState === WebSocket.OPEN) {
              socket.send("ping");
            }
          }, 20_000);
        }
      };
      socket.onmessage = (event) => {
        if (event.data === "pong") {
          return;
        }
        try {
          const candle = parseSocketCandle(socketExchange, JSON.parse(event.data));
          if (!candle || cancelled) {
            return;
          }
          seriesRef.current?.update(candle);
          setLastPrice(candle.close);
          onPriceUpdate?.(socketExchange === marketExchange ? candle.close : null);
          setConnectionState("live");
        } catch {
          // Ignore acknowledgement and unrelated exchange messages.
        }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        if (keepAliveTimer) {
          clearInterval(keepAliveTimer);
          keepAliveTimer = null;
        }
        if (cancelled) {
          return;
        }
        reconnectAttempt += 1;
        setConnectionState("reconnecting");
        if (!pollingTimer) {
          void pollLatestCandle();
          pollingTimer = setInterval(() => void pollLatestCandle(), 5_000);
        }
        reconnectTimer = setTimeout(
          () => connectSocket(activeMarketExchange),
          Math.min(1000 * 2 ** reconnectAttempt, 15_000),
        );
      };
    }

    void loadHistory().catch((error) => {
      if (!cancelled) {
        setConnectionState("error");
        setErrorMessage(error instanceof Error ? error.message : "行情加载失败");
      }
    });

    return () => {
      cancelled = true;
      socket?.close();
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
      }
      if (keepAliveTimer) {
        clearInterval(keepAliveTimer);
      }
      if (pollingTimer) {
        clearInterval(pollingTimer);
      }
    };
  }, [apiRoot, exchange, interval, onPriceUpdate, symbol, token]);

  return (
    <div className="live-market-chart">
      <div className="live-market-toolbar">
        <div className="live-market-intervals" aria-label="K 线周期">
          {(Object.keys(intervalLabels) as ChartInterval[]).map((value) => (
            <button
              className={interval === value ? "active" : ""}
              key={value}
              onClick={() => setIntervalValue(value)}
              type="button"
            >
              {intervalLabels[value]}
            </button>
          ))}
        </div>
        <div className={`live-market-state ${connectionState}`}>
          <span>{stateLabels[connectionState]}</span>
          <strong>{lastPrice === null ? "-" : lastPrice.toLocaleString("en-US")}</strong>
        </div>
      </div>
      <div ref={containerRef} className="live-market-canvas" aria-label={`${symbol} 实时 K 线图`} />
      {errorMessage && <p className="live-market-error">{errorMessage}</p>}
      <p className="live-market-source">
        行情来源：{(sourceExchange ?? exchange).toUpperCase()} 公开市场数据，无需 API 密钥
        {sourceExchange && sourceExchange !== exchange
          ? `（${exchange.toUpperCase()} 暂不可用，已自动切换；备用价格不用于下单预览）`
          : ""}
      </p>
    </div>
  );
}

function toChartCandle(value: CandlePayload): CandlestickData | null {
  if (
    !Number.isFinite(value.time) ||
    !Number.isFinite(value.open) ||
    !Number.isFinite(value.high) ||
    !Number.isFinite(value.low) ||
    !Number.isFinite(value.close)
  ) {
    return null;
  }
  return {
    time: value.time as UTCTimestamp,
    open: value.open,
    high: value.high,
    low: value.low,
    close: value.close,
  };
}

function isChartCandle(value: CandlestickData | null): value is CandlestickData {
  return value !== null;
}

function isLiveExchange(value: unknown): value is Exclude<ExchangeName, "mock"> {
  return value === "okx" || value === "binance" || value === "bybit";
}

function normalizedSymbol(symbol: string) {
  return symbol.replace("/", "").replace("-", "").toUpperCase();
}

function okxSymbol(symbol: string) {
  const normalized = normalizedSymbol(symbol);
  for (const quote of ["USDT", "USDC", "USD", "BTC", "ETH"]) {
    if (normalized.endsWith(quote)) {
      return `${normalized.slice(0, -quote.length)}-${quote}`;
    }
  }
  return normalized;
}

function webSocketUrl(exchange: Exclude<ExchangeName, "mock">, symbol: string, interval: ChartInterval) {
  if (exchange === "binance") {
    return `wss://stream.binance.com:9443/ws/${normalizedSymbol(symbol).toLowerCase()}@kline_${interval}`;
  }
  if (exchange === "bybit") {
    return "wss://stream.bybit.com/v5/public/spot";
  }
  return "wss://ws.okx.com:8443/ws/v5/business";
}

function subscriptionMessage(
  exchange: Exclude<ExchangeName, "mock">,
  symbol: string,
  interval: ChartInterval,
) {
  if (exchange === "binance") {
    return null;
  }
  if (exchange === "bybit") {
    const bybitInterval = { "1m": "1", "5m": "5", "15m": "15", "1h": "60" }[interval];
    return { op: "subscribe", args: [`kline.${bybitInterval}.${normalizedSymbol(symbol)}`] };
  }
  return { op: "subscribe", args: [{ channel: `candle${interval}`, instId: okxSymbol(symbol) }] };
}

function parseSocketCandle(
  exchange: Exclude<ExchangeName, "mock">,
  payload: Record<string, unknown>,
): CandlestickData | null {
  if (exchange === "binance") {
    const kline = payload.k as Record<string, unknown> | undefined;
    if (!kline) {
      return null;
    }
    return candleFromValues(kline.t, kline.o, kline.h, kline.l, kline.c);
  }
  if (exchange === "bybit") {
    const row = Array.isArray(payload.data) ? payload.data[0] as Record<string, unknown> | undefined : undefined;
    if (!row) {
      return null;
    }
    return candleFromValues(row.start, row.open, row.high, row.low, row.close);
  }
  const row = Array.isArray(payload.data) ? payload.data[0] as unknown[] | undefined : undefined;
  if (!row || row.length < 5) {
    return null;
  }
  return candleFromValues(row[0], row[1], row[2], row[3], row[4]);
}

function candleFromValues(
  timestamp: unknown,
  open: unknown,
  high: unknown,
  low: unknown,
  close: unknown,
): CandlestickData | null {
  const values = [Number(timestamp), Number(open), Number(high), Number(low), Number(close)];
  if (!values.every(Number.isFinite)) {
    return null;
  }
  return {
    time: Math.floor(values[0] / 1000) as UTCTimestamp,
    open: values[1],
    high: values[2],
    low: values[3],
    close: values[4],
  };
}
