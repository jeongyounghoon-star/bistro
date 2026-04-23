# Local setup — VS Code + Vercel workflow

End-to-end flow:

```
┌────────────────┐   ┌─────────────────────┐   ┌──────────────────────┐
│ collect_kr_    │ → │ run_kr_forecasts.py │ → │ web/public/data/     │
│ data.py        │   │ (BISTRO inference)  │   │   forecasts.json     │
└────────────────┘   └─────────────────────┘   └──────────┬───────────┘
                                                           │
                                             ┌─────────────▼──────────┐
                                             │ Next.js (web/) — Vercel│
                                             └────────────────────────┘
```

The Python pipeline runs locally (needs PyTorch + the BISTRO checkpoint).
The Next.js site only reads `forecasts.json`, so it deploys to Vercel as a
pure static-ish app.

---

## 1. Python environment (one-time)

```powershell
# from repo root, Windows PowerShell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt -r requirements-kr.txt
```

On macOS / Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt -r requirements-kr.txt
```

Python 3.11 is recommended (matches the notebooks).

## 2. Environment variables

Copy the example and keep `.env` local (it is gitignored):

```bash
cp .env.example .env
# edit .env and fill in DATA_GO_KR_API_KEY
```

## 3. Collect Korean data

```bash
python scripts/collect_kr_data.py              # Naver + data.go.kr
python scripts/collect_kr_data.py --naver-only # market data only
```

Output: CSVs in `data/kr/` (both daily and month-end aggregates).

Covered out of the box:

| Series                 | Source       | File                        |
| ---------------------- | ------------ | --------------------------- |
| KOSPI                  | Naver Finance | `naver_kospi_*.csv`        |
| 원/달러 환율           | Naver Finance | `naver_usdkrw_*.csv`       |
| 국고채 3Y / 10Y        | Naver Finance | `naver_ktb{3,10}y_*.csv`   |
| 회사채 AA- 3Y          | Naver Finance | `naver_corp_aa3y_*.csv`    |
| CD 91일                | Naver Finance | `naver_cd91_*.csv`         |
| USD/KRW (EXIM)         | data.go.kr   | `datagokr_usdkrw_*.csv`    |

For M2, 산업생산, 수출증가율, 주택가격지수(KB), 한은 BSI — subscribe to
the matching endpoints on data.go.kr, then either extend
`scripts/kr_data/datagokr.py` with a new fetcher or drop a hand-curated
CSV into `data/kr/` (`Date`, `Value` → first-column = date as YYYY-MM).

## 4. Run BISTRO forecasts

```bash
python scripts/run_kr_forecasts.py                 # all series
python scripts/run_kr_forecasts.py --ids kospi,usdkrw
python scripts/run_kr_forecasts.py --pdt 6 --ctx 120
```

Writes `web/public/data/forecasts.json` (history + median + 80% bands
per series). Uses the local `bistro-finetuned/` checkpoint — per
[VULNERABILITY_DISCLOSURE.md](VULNERABILITY_DISCLOSURE.md), do not
substitute external weights.

## 5. Web dashboard — local dev

```bash
cd web
npm install
npm run dev
# open http://localhost:3000
```

The page reads `web/public/data/forecasts.json` at render time. Re-run
the Python script and refresh the browser to see new forecasts.

## 6. Deploy to Vercel

Two options:

**A. GitHub integration (recommended).**

1. Commit the repo (including `web/public/data/forecasts.json`).
2. On vercel.com → "New Project" → import your GitHub repo.
3. Root Directory: leave blank — Vercel reads `vercel.json` and builds `web/`.
4. Framework preset: Next.js (auto-detected).
5. Deploy.

Every commit re-deploys. To refresh forecasts, re-run
`python scripts/run_kr_forecasts.py` locally and commit the updated JSON.

**B. Vercel CLI.**

```bash
npm i -g vercel
vercel                    # first time: link project
vercel --prod             # deploy
```

`.vercelignore` already excludes the heavy Python artifacts
(`bistro-finetuned/`, `data/`, `scripts/`) — only `web/` and the forecast
JSON ship to the edge.

## VS Code

`.vscode/launch.json` ships three ready-made run configs:

- *KR: collect data* — runs the Naver + data.go.kr collectors.
- *KR: run forecasts → forecasts.json* — full BISTRO pass.
- *KR: forecast single id (kr_cpi_yoy)* — quick single-series smoke test.

`.env` is loaded automatically via `envFile`.
