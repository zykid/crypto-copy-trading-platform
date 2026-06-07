const modules = [
  {
    title: "统一交易",
    text: "V1 阶段仅允许 MockExchange 与模拟模式，真实交易接口保持关闭。",
  },
  {
    title: "统一风控",
    text: "每笔订单进入执行前必须经过账户模式、交易开关、数量和金额限制检查。",
  },
  {
    title: "多租户隔离",
    text: "系统内部身份使用 user_id，业务查询必须绑定当前用户上下文。",
  },
  {
    title: "审计日志",
    text: "资金相关动作写入 append-only 审计记录，保留后续告警和追踪能力。",
  },
];

export default function Home() {
  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">多租户加密货币交易执行与跟单平台</div>
        <div className="status">SIMULATION ONLY</div>
      </header>
      <div className="main">
        <section className="section">
          <h1>V1.0 开发环境</h1>
          <p>
            当前前端为基础骨架，用于后续接入用户系统、授权共享、API Key 管理、
            MockExchange、风控和统一下单流程。
          </p>
        </section>
        <section className="grid" aria-label="platform modules">
          {modules.map((module) => (
            <article className="card" key={module.title}>
              <h2>{module.title}</h2>
              <p>{module.text}</p>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}
