import type { ForecastBundle } from "./types";

const PAPER_URL = "https://www.bis.org/publ/work1337.htm";
const REVIEW_URL = "https://www.bis.org/publ/qtrpdf/r_qt2603.pdf";

function countUniqueTags(bundle: ForecastBundle): number {
  return new Set(bundle.series.flatMap((series) => series.tags)).size;
}

function getLatestHistoryDate(bundle: ForecastBundle): string {
  const dates = bundle.series
    .flatMap((series) => series.history.map((point) => point.date))
    .sort();

  return dates[dates.length - 1] ?? "-";
}

function formatGeneratedAt(value: string): string {
  return new Date(value).toLocaleString("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export default function ResearchOverview({ bundle }: { bundle: ForecastBundle }) {
  const generatedAt = formatGeneratedAt(bundle.generated_at);
  const tagCount = countUniqueTags(bundle);
  const quarterlyCount = bundle.series.filter((series) => series.frequency === "Q").length;
  const monthlyCount = bundle.series.length - quarterlyCount;
  const latestActual = getLatestHistoryDate(bundle);

  return (
    <section className="overview-shell" aria-labelledby="dashboard-title">
      <div className="overview-bento">
        <article className="bento-card hero-card">
          <span className="eyebrow">BIS Time-series Regression Oracle</span>
          <h1 id="dashboard-title">BISTRO 한국 거시·금융 예측</h1>
          <p>
            한국 주요 거시·금융 지표의 최근 흐름과 12개월 중앙 예측 경로,
            80% 불확실성 구간을 한 화면에서 비교합니다.
          </p>
          <div className="hero-meta" aria-label="dashboard metadata">
            <span>생성 {generatedAt}</span>
            <span>최근 실측 {latestActual}</span>
            <span>{bundle.model}</span>
          </div>
          <div className="link-row">
            <a href={PAPER_URL} target="_blank" rel="noreferrer">
              Working Paper
            </a>
            <a href={REVIEW_URL} target="_blank" rel="noreferrer">
              Quarterly Review
            </a>
          </div>
        </article>

        <article className="bento-card metric-tile">
          <span>시계열</span>
          <strong>{bundle.series.length}</strong>
          <small>한국 지표</small>
        </article>
        <article className="bento-card metric-tile">
          <span>전망 기간</span>
          <strong>{bundle.horizon_months}개월</strong>
          <small>중앙 경로 + 밴드</small>
        </article>
        <article className="bento-card metric-tile">
          <span>입력 이력</span>
          <strong>{bundle.context_months}개월</strong>
          <small>모델 문맥</small>
        </article>
        <article className="bento-card metric-tile">
          <span>분류 태그</span>
          <strong>{tagCount}</strong>
          <small>필터 범주</small>
        </article>

        <article className="bento-card insight-card">
          <span className="eyebrow">Coverage</span>
          <h2>월간·분기 지표를 함께 추적</h2>
          <p>
            월간 {monthlyCount}개, 분기 {quarterlyCount}개 시계열을 같은 카드 규칙으로
            정리해 금리, 물가, 환율, 무역, 성장 흐름을 빠르게 읽을 수 있습니다.
          </p>
        </article>

        <article className="bento-card method-card">
          <span className="eyebrow">Signal</span>
          <h2>예측은 기준선으로 해석</h2>
          <p>
            파란색 중앙 경로는 BISTRO의 기준 전망이고, 반투명 밴드는 예측
            불확실성을 나타냅니다. 숫자 하나보다 방향과 범위를 함께 보는 구성입니다.
          </p>
        </article>
      </div>
    </section>
  );
}
