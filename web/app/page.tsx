import Dashboard from "./components/Dashboard";
import type { ForecastBundle } from "./components/types";
import forecastsData from "../public/data/forecasts.json";

export default function Home() {
  const bundle = forecastsData as ForecastBundle;

  return (
    <main className="container">
      <header className="site-header">
        <h1>BISTRO · 국내금융시장 예측 대시보드</h1>
        <p>
          BIS Time-series Regression Oracle로 한국 주요 거시/금융 시계열의
          12개월 확률적 전망(median · 80% 밴드)을 시각화합니다.
        </p>
        <div className="meta">
          최근 갱신: {new Date(bundle.generated_at).toLocaleString("ko-KR")} ·
          {" "}모델: {bundle.model} ·{" "}
          시계열: {bundle.series.length}개 · 예측 기간: {bundle.horizon_months}개월
        </div>
      </header>

      <Dashboard bundle={bundle} />
    </main>
  );
}
