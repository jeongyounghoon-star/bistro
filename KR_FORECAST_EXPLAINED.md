# BISTRO KR 예측 파이프라인 — 전체 설명

`scripts/run_kr_forecasts.py` 한 번 실행으로 **한국 거시·금융 14개 시계열**을 BISTRO(Moirai 파인튜닝) 모델에 넣어 12개월 예측을 만들고, 결과를 `web/public/data/forecasts.json`에 저장해 Next.js 대시보드(`web/`)가 그대로 그려줄 수 있도록 한 파이프라인이다.

```
┌──────────────────┐    ┌────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ 외부 API/스크래핑 │ →  │  data/kr/*.csv     │ →  │ run_kr_forecasts.py  │ →  │ forecasts.json (UTF8)│
│ ECOS / Naver      │    │ (14개, 2-col CSV)  │    │  Moirai inference    │    │  Next.js dashboard   │
└──────────────────┘    └────────────────────┘    └──────────────────────┘    └──────────────────────┘
   collect_kr_data.py        bistro convention         bistro-finetuned/                web/
```

---

## 1. 사용된 데이터 (14개 시리즈)

수집은 `scripts/collect_kr_data.py`가 담당하며, 두 곳에서 받아온다.

### 1-1. 한국은행 ECOS Open API (`scripts/kr_data/bok.py`)

ECOS REST 엔드포인트(`https://ecos.bok.or.kr/api/StatisticSearch/...`)를 호출해 받는다. 인증키는 `.env`의 `BOK_API_KEY`.

| 파일 | 시리즈 ID(SERIES_REGISTRY) | 통계코드 | 주기 | 단위 | 비고 |
|---|---|---|---|---|---|
| `bok_base_rate_d.csv` | `bok_base_rate` | 722Y001 | 일 → 월말 리샘플 | % | 한국은행 기준금리 |
| `bok_cpi_m.csv` | `bok_cpi` | 901Y009 | 월 | index | 소비자물가지수 (레벨) |
| `bok_unemployment_m.csv` | `bok_unemployment` | 901Y027/I61BC | 월 | % | 실업률 |
| `bok_m2_m.csv` | `bok_m2` | 161Y005/BBHS00 | 월 | 십억원 | M2 (평잔, 계절조정) |
| `bok_exports_m.csv` | `bok_exports` | 901Y118/T002 | 월 | 천달러 | 수출금액 |
| `bok_imports_m.csv` | `bok_imports` | 901Y118/T004 | 월 | 천달러 | 수입금액 |
| `bok_gdp_real_q.csv` | `bok_gdp_real` | 200Y104/1400 | 분기 → 월말 리샘플 | 십억원 | 실질 GDP |

### 1-2. Naver Finance 스크래핑 (`scripts/kr_data/naver_finance.py`)

브라우저 UA로 페이지 HTML을 받아 `pandas.read_html`로 표를 파싱, 일별 시계열을 만든 뒤 월말로 집계한다.

| 파일 (일/월) | 시리즈 ID | 단위 | 비고 |
|---|---|---|---|
| `naver_kospi_d/m.csv` | `kospi` | pt | KOSPI 종합지수 |
| `naver_usdkrw_d/m.csv` | `usdkrw` | KRW/USD | 원/달러 환율 |
| `naver_ktb3y_d/m.csv` | `ktb_3y` | % | 국고채 3년 |
| `naver_corp_aa3y_d/m.csv` | `corp_aa_3y` | % | 회사채 AA- 3년 |
| `naver_cd91_d/m.csv` | `cd_91` | % | CD 91일물 |

> 코멘트: KTB 10년물은 Naver의 `IRR_GOVT10Y` 페이지가 2026년 개편 이후 빈 표를 반환해 현재 레지스트리에서 제외돼 있다. 필요 시 ECOS에서 받도록 전환한다.

### 1-3. BIS (저장소에 이미 동봉)

| 파일 | 시리즈 ID | 단위 | 비고 |
|---|---|---|---|
| `data/bis_cpi_kr_yoy_m.csv` | `kr_cpi_yoy` | % | BIS long CPI YoY, 1966-01~ |
| `data/bis_cbpol_kr_m.csv` | `kr_policy_rate` | % | BIS 중앙은행 정책금리, 1999-05~ |

### CSV 포맷 규약 (BISTRO convention)

모든 CSV는 **2-column 형태**다.
- index 컬럼: 날짜 문자열 (e.g. `2000-01-01`, `2000-01`)
- 첫 번째 컬럼: 값

```csv
,base_rate
2000-01-01,4.75
2000-01-02,4.75
...
```

이 포맷이 `pd.read_csv(path, index_col=0)` 한 줄로 바로 로딩되도록 만들어진 게 핵심이다.

---

## 2. 모델 — BISTRO (Moirai 파인튜닝)

`bistro-finetuned/`에 가중치(`model.safetensors`) + 설정(`config.json`)이 있다. uni2ts의 `MoiraiForecast` / `MoiraiModule`로 로드한다.

### 아키텍처 요약 (`bistro-finetuned/config.json`)

| 항목 | 값 |
|---|---|
| 베이스 | Salesforce **Moirai** (universal time-series transformer) |
| `d_model` | 768 |
| `num_layers` | 12 |
| `max_seq_len` | 3120 |
| 지원 patch sizes | 8, 16, 32, 64, 128 |
| 출력 분포 | StudentT + NormalFixedScale(σ=0.001) + NegativeBinomial + LogNormal **혼합** |
| 스케일링 | 켜짐 (입력별 자동 정규화) |

Moirai는 *probabilistic* 모델이라 점추정 대신 **샘플 N개**를 뽑는다 (기본 100). 여기서 중앙값과 5/95 분위수로 신뢰구간을 만든다.

---

## 3. 전처리 → 추론 → 후처리 (`run_kr_forecasts.py`)

핵심 함수 두 개: `prepare_yoy_monthly_for_daily_inference` (전처리), `aggregate_daily_forecast_to_monthly` (후처리). 둘 다 `src/preprocessing_util.py`에 있다.

### 3-1. 시리즈 로딩 (`_load_series`)

1. CSV 읽기 → datetime index로 변환 → 정렬
2. **월말로 리샘플** (`resample("M").last()`): 일별·분기별을 모두 월 그리드로 통일
3. NaN 제거 후 `PeriodIndex(freq="M")`로 변환

→ 결과: 시리즈마다 `(N, 1)` 월간 데이터프레임. 60개월 미만이면 스킵된다.

### 3-2. "Daily inference" 트릭

Moirai는 토큰화 단위가 patch이다. 월간 데이터를 그대로 넣으면 patch가 너무 크게 잡힌다. 그래서 BISTRO 파이프라인은:

1. 월말 시점에 값을 둔 뒤 **patch_size_days(=32)만큼 forward-fill**해 **일별** 시계열로 확장
2. `psz=32`, 즉 **32개의 일자가 한 patch**가 되도록 모델에 전달
3. 미래 호라이즌만큼 `pad_future_markers`로 -1/-2 마커를 끼워 넣어, 슬라이딩 윈도우의 horizon이 항상 확보되도록 한다

이 방식의 이점은 *월간 시리즈를 일간으로 학습된 Moirai의 표현력*에 그대로 태울 수 있다는 점이다.

### 3-3. 이번 실행에 사용된 추론 파라미터

`scripts/run_kr_forecasts.py`의 CLI 기본값을 그대로 사용했다.

| 인자 | 값 | 의미 |
|---|---|---|
| `--pdt` | 12 | 예측 horizon (월 수) |
| `--ctx` | 240 | 컨텍스트 길이 (월). 시리즈가 짧으면 `min(ctx, len-pdt-12)`로 자동 축소 |
| `--psz` | 32 | patch size (일) — 월 1개 ≈ 32일 |
| `--bsz` | 32 | 배치 크기 |
| `--num-samples` | 100 | 분포 샘플 수 |

내부적으로는 일 단위로 환산되어:
- `pdt_steps = 32 × 12 = 384일`
- `ctx_steps = 32 × 240 = 7,680일` (시리즈 길이만큼만 사용)

### 3-4. 추론 흐름 (시리즈 1개당)

```
df_monthly (PeriodIndex, M)
   │ prepare_yoy_monthly_for_daily_inference
   ▼
daily_df (DatetimeIndex, D, ffilled, 미래 패딩 포함)
   │ PandasDataset → split(date=cutoff)
   ▼
test_template.generate_instances(prediction_length, windows, distance, max_history)
   │ MoiraiForecast.create_predictor(batch_size).predict(...)
   ▼
forecasts[0].samples  ← shape (num_samples, pdt_steps)  e.g. (100, 384)
   │ aggregate_daily_forecast_to_monthly
   ▼
preds (12,), ci (12, 2)  ← 일간 샘플을 월 segment(=patch)로 묶어 평균 → 분위수
```

`aggregate_daily_forecast_to_monthly`는 라벨 마커(`np.repeat(arange(pdt), psz)`)에서 변화점을 찾아 horizon을 12개의 월 segment로 자른 뒤, 각 segment 안의 평균을 샘플별로 계산하고 그 분포에서 **median, p5, p95**를 뽑아낸다.

### 3-5. 결과 페이로드 빌드

각 시리즈마다 다음을 누적:
- `history`: 마지막 180개월(`tail_months=180`)을 `{date: "YYYY-MM", value}` 리스트로
- `forecast`: 12개월 예측을 `{date, median, lo, hi}` 리스트로
- 메타: `id`, `title`, `unit`, `frequency`, `tags`, `note`, `forecast_start`

번들 헤더에 `generated_at` (ISO8601 UTC), `model = "BISTRO (Moirai fine-tuned)"`, `horizon_months`, `context_months`를 붙여 JSON으로 직렬화한다.

---

## 4. 이번 실행 결과 (2026-04-23)

```
입력  : data/kr/*.csv (14개) + data/bis_*.csv (2개)
모델  : bistro-finetuned/  (Moirai universal TS transformer)
디바이스: CPU (torch 2.10.0+cpu)
horizon: 12개월, context: 최대 240개월, num_samples: 100
출력  : web/public/data/forecasts.json (212 KB, UTF-8)
소요  : 약 23초 (14 시리즈 직렬 처리, CPU)
```

| 시리즈 | rows(months) | forecast_start |
|---|---|---|
| kr_cpi_yoy / kr_policy_rate | 720 / 320 | 2026-01 |
| kospi | 118 | 2026-05 |
| usdkrw / bok_base_rate | 195 / 316 | 2026-05 |
| ktb_3y / corp_aa_3y / cd_91 | 137 | 2026-05 |
| bok_cpi / bok_unemployment | 315 | 2026-04 |
| bok_m2 / bok_exports / bok_imports | 269 / 314 | 2026-03 |
| bok_gdp_real (분기 → 월말) | 104 | 2025-11 |

**14/14 시리즈 모두 성공.** 콘솔 한글 깨짐은 Windows cp949 stdout 인코딩 때문이고, 저장된 JSON은 `ensure_ascii=False`로 UTF-8 한글이 그대로 들어간다.

---

## 5. 재현 방법

```bash
# 1) (선택) 데이터 다시 수집  -- ECOS / Naver 키 필요
python scripts/collect_kr_data.py

# 2) 예측 실행 (기본값: 14개 전체, 12개월 horizon)
python scripts/run_kr_forecasts.py

# 부분 실행 / 파라미터 조정 예시
python scripts/run_kr_forecasts.py --ids kospi,usdkrw
python scripts/run_kr_forecasts.py --pdt 6 --ctx 120 --num-samples 200

# 3) 웹 미리보기
cd web && npm run dev   # → http://localhost:3000
```

### 산출물 위치

| 경로 | 설명 |
|---|---|
| `data/kr/*.csv` | 수집 원본 (BOK + Naver) |
| `web/public/data/forecasts.json` | 모든 시리즈의 history + 12M forecast 번들 |
| `bistro-finetuned/` | Moirai 파인튜닝 가중치 (변경 없음) |

### 출력 JSON 스키마 (요약)

```json
{
  "generated_at": "2026-04-23T08:56:15+00:00",
  "model": "BISTRO (Moirai fine-tuned)",
  "horizon_months": 12,
  "context_months": 240,
  "series": [
    {
      "id": "kospi",
      "title": "KOSPI 종합지수",
      "unit": "pt",
      "frequency": "M",
      "tags": ["주식"],
      "note": "",
      "forecast_start": "2026-05",
      "history":  [{"date": "YYYY-MM", "value": 0.0}, ...],     // 최대 180개
      "forecast": [{"date": "YYYY-MM", "median": 0.0,           // 12개
                    "lo": 0.0, "hi": 0.0}, ...]
    }
  ]
}
```

`lo`/`hi`는 일간 샘플을 월 단위로 평균한 분포의 **5/95 분위수**(약 90% 신뢰구간).

---

## 6. 디렉토리 맵 (관련 파일만)

```
bistro/
├─ scripts/
│  ├─ collect_kr_data.py          # 데이터 수집 CLI
│  ├─ run_kr_forecasts.py         # 예측 실행 + JSON 빌드 ← 이번 실행 진입점
│  └─ kr_data/
│     ├─ bok.py                   # ECOS 클라이언트
│     ├─ naver_finance.py         # Naver 스크래퍼
│     ├─ datagokr.py              # 공공데이터포털 클라이언트
│     └─ common.py                # 경로/키 헬퍼
├─ src/
│  ├─ preprocessing_util.py       # daily 변환, padding, 후처리 집계
│  └─ inference_util.py
├─ data/
│  ├─ bis_*.csv                   # BIS 동봉 시리즈
│  └─ kr/*.csv                    # 수집된 한국 시리즈
├─ bistro-finetuned/
│  ├─ config.json                 # Moirai 아키텍처 설정
│  └─ model.safetensors           # 파인튜닝 가중치
└─ web/
   ├─ app/                        # Next.js App Router
   └─ public/data/forecasts.json  # 대시보드가 fetch하는 산출물
```
