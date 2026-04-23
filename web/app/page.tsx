import path from "node:path";
import fs from "node:fs/promises";
import Dashboard from "./components/Dashboard";
import type { ForecastBundle } from "./components/types";

async function loadBundle(): Promise<ForecastBundle | null> {
  const p = path.join(process.cwd(), "public", "data", "forecasts.json");
  try {
    const raw = await fs.readFile(p, "utf-8");
    return JSON.parse(raw) as ForecastBundle;
  } catch {
    return null;
  }
}

export default async function Home() {
  const bundle = await loadBundle();

  return (
    <main className="container">
      <header className="site-header">
        <h1>BISTRO · 국내금융시장 예측 대시보드</h1>
        <p>
          BIS Time-series Regression Oracle로 한국 주요 거시/금융 시계열의
          12개월 확률적 전망(median · 80% 밴드)을 시각화합니다.
        </p>
        {bundle && (
          <div className="meta">
            최근 갱신: {new Date(bundle.generated_at).toLocaleString("ko-KR")} ·
            {" "}모델: {bundle.model} ·{" "}
            시계열: {bundle.series.length}개 · 예측 기간: {bundle.horizon_months}개월
          </div>
        )}
      </header>

      {bundle ? (
        <Dashboard bundle={bundle} />
      ) : (
        <div className="empty">
          <p><strong>forecasts.json을 찾을 수 없습니다.</strong></p>
          <p>
            레포 루트에서 다음 명령으로 생성하세요:{" "}
            <code>python scripts/run_kr_forecasts.py</code>
          </p>
        </div>
      )}
    </main>
  );
}
