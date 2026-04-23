"""Run BISTRO forecasts across Korean series and write a JSON bundle for the web app.

Inputs:
  - Any CSV in data/ or data/kr/ registered in SERIES_REGISTRY below.
  - Two-column CSV format (BISTRO convention): index = date, first column = value.

Output:
  - web/public/data/forecasts.json

Usage:
    python scripts/run_kr_forecasts.py
    python scripts/run_kr_forecasts.py --ids kr_cpi_yoy,kospi
    python scripts/run_kr_forecasts.py --pdt 6 --ctx 120
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from kr_data.common import forecast_json_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeriesSpec:
    id: str
    title: str
    csv: str
    unit: str
    frequency: str = "M"
    tags: list[str] = field(default_factory=list)
    note: str = ""


SERIES_REGISTRY: list[SeriesSpec] = [
    SeriesSpec(
        id="kr_cpi_yoy",
        title="한국 CPI (YoY)",
        csv="data/bis_cpi_kr_yoy_m.csv",
        unit="%",
        tags=["물가", "거시"],
        note="BIS long CPI, 1966-01~",
    ),
    SeriesSpec(
        id="kr_policy_rate",
        title="한국 정책금리",
        csv="data/bis_cbpol_kr_m.csv",
        unit="%",
        tags=["금리", "통화정책"],
        note="BIS central bank policy rate, 1999-05~",
    ),
    SeriesSpec(
        id="kospi",
        title="KOSPI 종합지수",
        csv="data/kr/naver_kospi_m.csv",
        unit="pt",
        tags=["주식"],
    ),
    SeriesSpec(
        id="usdkrw",
        title="원/달러 환율",
        csv="data/kr/naver_usdkrw_m.csv",
        unit="KRW/USD",
        tags=["환율"],
    ),
    SeriesSpec(
        id="ktb_3y",
        title="국고채 3년",
        csv="data/kr/naver_ktb3y_m.csv",
        unit="%",
        tags=["금리", "채권"],
    ),
    # ktb_10y: Naver's IRR_GOVT10Y endpoint has been returning empty tables
    # since the 2026 page revamp. Source from BOK ECOS when needed.
    SeriesSpec(
        id="corp_aa_3y",
        title="회사채 AA- 3년",
        csv="data/kr/naver_corp_aa3y_m.csv",
        unit="%",
        tags=["금리", "크레딧"],
    ),
    SeriesSpec(
        id="cd_91",
        title="CD 91일물",
        csv="data/kr/naver_cd91_m.csv",
        unit="%",
        tags=["금리", "단기"],
    ),
    SeriesSpec(
        id="bok_base_rate",
        title="한국은행 기준금리",
        csv="data/kr/bok_base_rate_d.csv",
        unit="%",
        tags=["금리", "통화정책"],
        note="ECOS 722Y001, daily → month-end",
    ),
    SeriesSpec(
        id="bok_cpi",
        title="소비자물가지수 (레벨)",
        csv="data/kr/bok_cpi_m.csv",
        unit="index",
        tags=["물가", "거시"],
        note="ECOS 901Y009",
    ),
    SeriesSpec(
        id="bok_unemployment",
        title="실업률",
        csv="data/kr/bok_unemployment_m.csv",
        unit="%",
        tags=["고용", "거시"],
        note="ECOS 901Y027/I61BC",
    ),
    SeriesSpec(
        id="bok_m2",
        title="M2 (평잔, 계절조정)",
        csv="data/kr/bok_m2_m.csv",
        unit="십억원",
        tags=["통화", "거시"],
        note="ECOS 161Y005/BBHS00",
    ),
    SeriesSpec(
        id="bok_exports",
        title="수출금액",
        csv="data/kr/bok_exports_m.csv",
        unit="천달러",
        tags=["무역"],
        note="ECOS 901Y118/T002",
    ),
    SeriesSpec(
        id="bok_imports",
        title="수입금액",
        csv="data/kr/bok_imports_m.csv",
        unit="천달러",
        tags=["무역"],
        note="ECOS 901Y118/T004",
    ),
    SeriesSpec(
        id="bok_gdp_real",
        title="실질 GDP (분기)",
        csv="data/kr/bok_gdp_real_q.csv",
        unit="십억원",
        frequency="Q",
        tags=["거시", "GDP"],
        note="ECOS 200Y104/1400, resampled to month-end",
    ),
]


def _load_series(spec: SeriesSpec) -> pd.DataFrame | None:
    path = (REPO_ROOT / spec.csv).resolve()
    if not path.exists():
        logger.warning("Skip %s: CSV not found at %s", spec.id, path)
        return None
    df = pd.read_csv(path, index_col=0)
    if df.empty or df.shape[1] == 0:
        logger.warning("Skip %s: empty CSV", spec.id)
        return None
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[~df.index.isna()]
    df = df.sort_index()
    value_col = df.columns[0]
    monthly = df[[value_col]].resample("M").last().dropna()
    monthly.index = monthly.index.to_period("M")
    return monthly


def _forecast_one(df: pd.DataFrame, *, pdt: int, ctx: int, psz: int, bsz: int, num_samples: int):
    """Run BISTRO on a single monthly series. Returns (forecast_df, forecast_start_period)."""
    from gluonts.dataset.pandas import PandasDataset
    from gluonts.dataset.split import split
    from uni2ts.model.moirai import MoiraiForecast, MoiraiModule

    from preprocessing_util import (
        aggregate_daily_forecast_to_monthly,
        prepare_yoy_monthly_for_daily_inference,
    )

    target_col = df.columns[0]
    last_period = df.index.max()
    forecast_start_date = (last_period + 1).to_timestamp().strftime("%Y-%m-%d")

    usable_ctx = min(ctx, max(36, len(df) - pdt - 12))

    prep = prepare_yoy_monthly_for_daily_inference(
        df,
        target_col=target_col,
        freq="M",
        forecast_start_date=forecast_start_date,
        pdt_patches=pdt,
        ctx_patches=usable_ctx,
        steps_per_period=psz,
        rolling_windows=1,
        window_distance_patches=1,
    )

    ds = PandasDataset(prep.daily_df, target=target_col)
    _, test_template = split(ds, date=prep.cutoff_period_daily)
    # prep.windows is computed from unpadded history: when we forecast purely
    # out-of-sample (cutoff = last observation), it evaluates to 0. Padding
    # gives the template a valid horizon, so force at least one window.
    windows = max(1, int(prep.windows))
    test_data = test_template.generate_instances(
        prediction_length=prep.pdt_steps,
        windows=windows,
        distance=prep.dist_steps,
        max_history=prep.ctx_steps,
    )

    model_repo = REPO_ROOT / "bistro-finetuned"
    model = MoiraiForecast(
        module=MoiraiModule.from_pretrained(str(model_repo)),
        prediction_length=int(prep.pdt_steps),
        context_length=int(prep.ctx_steps),
        patch_size=int(psz),
        num_samples=int(num_samples),
        target_dim=1,
        feat_dynamic_real_dim=0,
        past_feat_dynamic_real_dim=0,
    )

    predictor = model.create_predictor(batch_size=bsz)
    inputs = list(test_data.input)
    forecasts = list(predictor.predict(test_data.input))

    samples = np.asarray(forecasts[0].samples, dtype=float)
    inp_target = np.asarray(inputs[0]["target"], dtype=float)
    last_input = float(inp_target[-1]) if inp_target.size else None

    # aggregate_daily_forecast_to_monthly segments the daily forecast into
    # monthly predictions using change points in the label array. For pure
    # future forecasting we have no ground truth, so synthesize a label with
    # `pdt` distinct segments of `psz` days each (indices 0..pdt-1 repeated).
    label_markers = np.repeat(np.arange(pdt, dtype=float), psz)

    preds, _, ci = aggregate_daily_forecast_to_monthly(
        samples,
        label_markers,
        last_input,
        steps_per_period=psz,
        expected_periods=pdt,
    )

    idx = pd.period_range(start=prep.forecast_start, periods=pdt, freq="M")
    fc_df = pd.DataFrame(
        {"median": preds, "lo": ci[:, 0], "hi": ci[:, 1]},
        index=idx,
    )
    return fc_df, prep.forecast_start


def _history_payload(df: pd.DataFrame, tail_months: int = 180) -> list[dict]:
    t = df.tail(tail_months)
    col = t.columns[0]
    return [
        {"date": p.strftime("%Y-%m"), "value": float(v)}
        for p, v in t[col].items()
    ]


def _forecast_payload(fc: pd.DataFrame) -> list[dict]:
    return [
        {
            "date": p.strftime("%Y-%m"),
            "median": float(r["median"]),
            "lo": float(r["lo"]),
            "hi": float(r["hi"]),
        }
        for p, r in fc.iterrows()
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", help="Comma-separated series ids (default: all)")
    parser.add_argument("--pdt", type=int, default=12)
    parser.add_argument("--ctx", type=int, default=240)
    parser.add_argument("--psz", type=int, default=32)
    parser.add_argument("--bsz", type=int, default=32)
    parser.add_argument("--num-samples", type=int, default=100)
    parser.add_argument("--output", help="Override JSON output path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    selected = set(args.ids.split(",")) if args.ids else None
    specs = [s for s in SERIES_REGISTRY if selected is None or s.id in selected]

    results: list[dict] = []
    for spec in specs:
        df = _load_series(spec)
        if df is None or len(df) < 60:
            logger.warning("Skip %s: not enough data (%s rows)", spec.id, 0 if df is None else len(df))
            continue
        try:
            logger.info("Forecasting %s (rows=%d)...", spec.id, len(df))
            fc, start = _forecast_one(
                df,
                pdt=args.pdt,
                ctx=args.ctx,
                psz=args.psz,
                bsz=args.bsz,
                num_samples=args.num_samples,
            )
        except Exception as e:
            logger.exception("Forecast failed for %s: %s", spec.id, e)
            continue
        results.append({
            "id": spec.id,
            "title": spec.title,
            "unit": spec.unit,
            "frequency": spec.frequency,
            "tags": spec.tags,
            "note": spec.note,
            "forecast_start": start.strftime("%Y-%m"),
            "history": _history_payload(df),
            "forecast": _forecast_payload(fc),
        })

    out_path = Path(args.output).resolve() if args.output else forecast_json_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": "BISTRO (Moirai fine-tuned)",
        "horizon_months": args.pdt,
        "context_months": args.ctx,
        "series": results,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote %d series to %s", len(results), out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
