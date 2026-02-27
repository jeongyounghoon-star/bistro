import logging
import numpy as np
import pandas as pd
from typing import Literal

logger = logging.getLogger(__name__)

def entry_start_end(entry, freq: str):
    """Return (start_period, end_period) for a gluonts DataEntry."""
    s = entry["start"]
    n = len(entry["target"])
    if isinstance(s, pd.Period):
        if s.freqstr != freq:
            raise ValueError(f"Entry start freq mismatch: {s.freqstr} != {freq}")
        start = s
    else:
        if not freq:
            raise ValueError("Missing frequency for entry_start_end.")
        start = pd.Period(pd.Timestamp(s), freq=freq)
    e = start + (n - 1)
    return start, e

def forecast_period_index(fcst, H, freq: str):
    """Return PeriodIndex for forecast horizon."""
    s = fcst.start_date
    if isinstance(s, pd.Period):
        if s.freqstr != freq:
            raise ValueError(f"Forecast start freq mismatch: {s.freqstr} != {freq}")
        start = s
    else:
        if not freq:
            raise ValueError("Missing frequency for forecast_period_index.")
        start = pd.Period(pd.Timestamp(s), freq=freq)
    return pd.period_range(start=start, periods=H, freq=freq)

def period_range_from_start(start, length):
    """Return DatetimeIndex starting at a period/timestamp for length periods."""
    if isinstance(start, pd.Period):
        return pd.period_range(start=start, periods=length, freq=start.freq).to_timestamp()
    start = pd.Timestamp(start)
    return pd.date_range(start=start, periods=length, freq="MS")

def build_window_table(inputs, labels, forecasts, agg="median"):
    """
    Wide table:
      row = window
      columns = metadata + pred_<YYYY-MM> (shared across windows)
    agg: 'median' or 'mean'
    """
    rows = []
    all_pred_periods = set()

    for w, (inp, lab, fcst) in enumerate(zip(inputs, labels, forecasts)):
        freq = None
        for candidate in (fcst.start_date, inp.get("start"), lab.get("start")):
            if isinstance(candidate, pd.Period):
                freq = candidate.freqstr
                break
        if not freq:
            raise ValueError("Missing frequency: expected Period start in inputs/labels/forecasts.")

        in_s, in_e = entry_start_end(inp, freq)
        te_s, te_e = entry_start_end(lab, freq)

        samples = np.asarray(fcst.samples)      # (S, H)
        H = samples.shape[1]

        if agg == "mean":
            pred = samples.mean(axis=0)
        else:
            pred = np.median(samples, axis=0)

        pidx = forecast_period_index(fcst, H, freq)   # PeriodIndex length H
        all_pred_periods.update(pidx)

        row = {
            "window": w,
            "train_start": in_s,
            "train_end": in_e,
            "test_start": te_s,
            "test_end": te_e,
            "freq": freq,
        }

        # put predictions into shared date columns
        for per, val in zip(pidx, pred):
            row[f"pred_{per.to_timestamp().strftime('%Y-%m-%d')}"] = float(val)

        rows.append(row)

    df_out = pd.DataFrame(rows)

    # order columns: metadata first, then pred columns in chronological order
    pred_periods_sorted = sorted(all_pred_periods)
    pred_cols_sorted = [f"pred_{p.to_timestamp().strftime('%Y-%m-%d')}" for p in pred_periods_sorted]

    meta_cols = ["window", "train_start", "train_end", "test_start", "test_end", "freq"]
    other_cols = [c for c in pred_cols_sorted if c in df_out.columns]

    df_out = df_out[meta_cols + other_cols]
    return df_out

def plot_forecast_windows(df, forecasts, target_col=None, figsize=(18, 6)):
    """
    Overlay actual series with all forecast windows and quantile bands.
    """
    import matplotlib.pyplot as plt

    if target_col is None:
        target_col = df.columns[0]

    full_x = df.index.to_timestamp()
    full_y = df[target_col].to_numpy()

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(full_x, full_y, color="black", lw=1.4, label="actual")

    for fcst in forecasts:
        samples = np.asarray(fcst.samples)      # (num_samples, H)
        H = samples.shape[1]                    # <-- use actual horizon

        p50 = np.median(samples, axis=0)
        p10 = np.quantile(samples, 0.10, axis=0)
        p90 = np.quantile(samples, 0.90, axis=0)

        fc_x = period_range_from_start(fcst.start_date, H)

        ax.fill_between(fc_x, p10, p90, color="C0", alpha=0.06, linewidth=0)
        ax.plot(fc_x, p50, color="C0", alpha=0.22, lw=1.0)

    ax.set_title(
        f"Overlay of all forecast windows (windows={len(forecasts)}, horizon={samples.shape[1]})"
    )
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left")
    plt.tight_layout()
    plt.show()

    return fig, ax

def plot_publication_forecast_comparison(
    df,
    *,
    actual_col=None,
    forecast_cols=None,
    forecast_start=None,
    title=None,
    ylabel=None,
    y_fmt=None,
    percent_scale=1.0,
    figsize=(7.5, 3.8),
    dpi=300,
    source_note=None,
    savepaths=None,
):
    """
    Publication-style time series plot: actual series vs one or more forecast series.

    - df: DataFrame with PeriodIndex or DatetimeIndex
    - actual_col: column name for the realised series (defaults to first column)
    - forecast_cols: dict {col_name: label} for forecast series to overlay
    - forecast_start: date-like; draws a vertical line and shades forecast region
    - y_fmt: None or "percent" (uses PercentFormatter with xmax=percent_scale)
    - savepaths: optional list of output paths (e.g., PDF/PNG)
    """
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    from pathlib import Path

    if actual_col is None:
        actual_col = df.columns[0]
    if forecast_cols is None:
        forecast_cols = {}

    if isinstance(df.index, pd.PeriodIndex):
        x = df.index.to_timestamp()
        idx_freq = df.index.freqstr
    else:
        x = pd.DatetimeIndex(df.index)
        idx_freq = None

    def _to_ts(v):
        if v is None:
            return None
        if isinstance(v, pd.Period):
            return v.to_timestamp()
        ts = pd.Timestamp(v)
        if idx_freq:
            return pd.Period(ts, freq=idx_freq).to_timestamp()
        return ts

    fc_start_ts = _to_ts(forecast_start)

    rc = {
        "figure.dpi": dpi,
        "savefig.dpi": dpi,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "xtick.labelsize": 8,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "font.family": "DejaVu Sans",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }

    with plt.rc_context(rc):
        fig, ax = plt.subplots(figsize=figsize, constrained_layout=True)

        ax.plot(
            x,
            df[actual_col].to_numpy(dtype=float),
            color="black",
            lw=2.0,
            label="Actual",
            zorder=3,
        )

        cmap = plt.get_cmap("tab10")
        for i, (col, label) in enumerate(forecast_cols.items()):
            if col not in df.columns:
                raise KeyError(f"Missing forecast column: {col}")
            ax.plot(
                x,
                df[col].to_numpy(dtype=float),
                lw=1.8,
                color=cmap(i),
                label=label,
                zorder=2,
            )

        if fc_start_ts is not None:
            ax.axvline(fc_start_ts, color="0.35", lw=1.0, ls="--", zorder=1)
            ax.axvspan(fc_start_ts, x.max(), color="0.75", alpha=0.14, zorder=0)

        ax.grid(True, axis="y", color="0.86", linewidth=0.8)
        ax.set_axisbelow(True)

        if title:
            ax.set_title(title)
        if ylabel:
            ax.set_ylabel(ylabel)

        if y_fmt == "percent":
            ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=percent_scale))

        span_months = max(1, int(round((x.max() - x.min()).days / 30.4)))
        if span_months <= 36:
            ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%y-%m"))
        else:
            ax.xaxis.set_major_locator(mdates.YearLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

        ax.legend(loc="upper left", frameon=False, ncol=2)

        if source_note:
            fig.text(0.01, 0.01, source_note, ha="left", va="bottom", fontsize=9, color="0.35")

        if savepaths:
            for sp in savepaths:
                out = Path(sp)
                if out.parent and str(out.parent) not in (".", ""):
                    out.parent.mkdir(parents=True, exist_ok=True)
                fig.savefig(out, bbox_inches="tight")

        return fig, ax

def rmse(yhat, y):
    """Root mean squared error (RMSE) after aligning time indices."""
    err = yhat - y
    return float(np.sqrt(np.mean(err ** 2)))

def _fit_ar1(
    y: pd.Series,
    *,
    method: Literal["statsmodels", "ols"] = "statsmodels",
    trend: Literal["c", "n"] = "c",
):
    y = pd.Series(y).dropna()
    if len(y) < 3:
        raise ValueError("Need at least 3 observations to fit AR(1).")

    if method == "statsmodels":
        try:
            from statsmodels.tsa.ar_model import AutoReg
        except Exception as e:  # pragma: no cover
            raise ImportError(
                "statsmodels is required for method='statsmodels'. Install statsmodels or use method='ols'."
            ) from e

        fit = AutoReg(y, lags=1, trend=trend, old_names=False).fit()
        params = fit.params.to_dict() if hasattr(fit.params, "to_dict") else dict(fit.params)

        lag_keys = [k for k in params.keys() if str(k).endswith(".L1")]
        if len(lag_keys) != 1:
            raise ValueError(f"Unexpected AR(1) params; expected single lag term, got keys={list(params.keys())}")
        lag_key = lag_keys[0]

        if trend == "c":
            c = float(params.get("const", 0.0))
            phi = float(params.get(lag_key))
        else:
            c = 0.0
            phi = float(params.get(lag_key))
        return c, phi

    if trend == "c":
        y_lag = y.shift(1).dropna()
        y_cur = y.loc[y_lag.index]
        X = np.column_stack([np.ones(len(y_lag)), y_lag.to_numpy(dtype=float)])
        beta, *_ = np.linalg.lstsq(X, y_cur.to_numpy(dtype=float), rcond=None)
        return float(beta[0]), float(beta[1])

    y_lag = y.shift(1).dropna()
    y_cur = y.loc[y_lag.index]
    X = np.column_stack([y_lag.to_numpy(dtype=float)])
    beta, *_ = np.linalg.lstsq(X, y_cur.to_numpy(dtype=float), rcond=None)
    return 0.0, float(beta[0])


def ar1_forecast(
    y: pd.Series,
    forecast_index,
    *,
    method: Literal["statsmodels", "ols"] = "statsmodels",
    trend: Literal["c", "n"] = "c",
    validate_index: bool = True,
):
    """Fit an AR(1) on `y` and generate dynamic forecasts for `forecast_index`.

    AR(1): y_t = c + phi * y_{t-1} + e_t

    Important: `forecast_index[0]` must be one period after the last observation in `y`.
    """
    y = pd.Series(y).dropna()
    if len(y) < 3:
        raise ValueError("Need at least 3 observations to fit AR(1).")

    forecast_index = pd.Index(forecast_index)
    if forecast_index.has_duplicates:
        raise ValueError("forecast_index must not contain duplicates.")
    if len(forecast_index) == 0:
        return pd.Series([], dtype=float, index=forecast_index)
    if not forecast_index.is_monotonic_increasing:
        raise ValueError("forecast_index must be monotonic increasing.")

    if validate_index and isinstance(y.index, pd.PeriodIndex) and isinstance(forecast_index, pd.PeriodIndex):
        if y.index.freqstr != forecast_index.freqstr:
            raise ValueError(f"Frequency mismatch: y={y.index.freqstr} vs forecast_index={forecast_index.freqstr}")
        expected_start = y.index[-1] + 1
        if forecast_index[0] != expected_start:
            raise ValueError(
                f"forecast_index must start at y.index[-1] + 1 ({expected_start}), got {forecast_index[0]}"
            )

    c, phi = _fit_ar1(y, method=method, trend=trend)

    last = float(y.iloc[-1])
    fc_vals = []
    for _ in range(len(forecast_index)):
        last = c + phi * last
        fc_vals.append(last)

    return pd.Series(fc_vals, index=forecast_index, dtype=float)

def r_rmse(yhat, y, yhat_benchmark):
    """Relative RMSE (R-RMSE): RMSE(model) divided by RMSE(benchmark)."""
    denom = rmse(yhat_benchmark, y)
    if denom == 0:
        raise ZeroDivisionError("Benchmark RMSE is zero.")
    return rmse(yhat, y) / denom

def calculate_rmse(
    df,
    result_table,
    *,
    ar_ctx: int | None = None,
    ar_method: Literal["statsmodels", "ols"] = "statsmodels",
    ar_trend: Literal["c", "n"] = "c",
):
    """
    Calculates RMSE metrics for predicted and AR1-forecasted values over specified test periods in the result_table.
    Returns a DataFrame summarizing RMSE statistics for each test interval.
    """
    
    if "freq" not in result_table.columns:
        raise ValueError("Missing frequency in result_table.")
    freq_vals = result_table["freq"].dropna().unique().tolist()
    if len(freq_vals) != 1:
        raise ValueError(f"Expected single frequency in result_table, got: {freq_vals}")
    freq = freq_vals[0]

    result_rmse = []
    for idx, rec in result_table.iterrows():
        try:
            resrec = rec.copy()
            date_start = resrec["test_start"]
            date_end = resrec["test_end"]
            resrec_predval = resrec.loc[[x for x in resrec.index if x.startswith("pred")]]

            resrec_predval.index = pd.to_datetime([x[5:] for x in resrec_predval.index]).to_period(freq=freq)
            resrec_predval = resrec_predval.loc[date_start:date_end].sort_index()

            resrec_answer = df.loc[date_start:date_end].copy().iloc[:, 0].sort_index()
            if isinstance(resrec_answer.index, pd.PeriodIndex) and resrec_answer.index.freqstr != freq:
                raise ValueError(f"Actual series freq mismatch: {resrec_answer.index.freqstr} != {freq}")

            has_nan = resrec_answer.isna().any()
            yyhat_tuple = resrec_answer.align(resrec_predval, join="inner")

            ydate = yyhat_tuple[0].index
            y_ts = yyhat_tuple[0]  # for AR1
            y = yyhat_tuple[0].to_numpy(dtype=float)
            yhat = yyhat_tuple[1].to_numpy(dtype=float)

            logger.info(
                "rmse_window idx=%s start=%s end=%s pred_len=%s actual_len=%s aligned_len=%s has_nan=%s",
                idx,
                date_start,
                date_end,
                len(resrec_predval),
                len(resrec_answer),
                len(y),
                has_nan,
            )

            if len(y) == 0:
                logger.info(
                    "Skipping RMSE window with no valid values: idx=%s start=%s end=%s",
                    idx,
                    date_start,
                    date_end,
                )
                continue

            rmse_bistro = rmse(yhat, y)

            try:
                train_start = resrec["train_start"]
                train_end = resrec["train_end"]
                train_y = df.loc[train_start:train_end].copy().iloc[:, 0].sort_index()
                if ar_ctx is not None:
                    train_y = train_y.tail(int(ar_ctx))

                ar1_series = ar1_forecast(
                    train_y,
                    ydate,
                    method=ar_method,
                    trend=ar_trend,
                    validate_index=True,
                )
                ar1_pred = ar1_series.to_numpy(dtype=float)
                rmse_ar1 = rmse(ar1_pred, y)
                if rmse_ar1 == 0:
                    raise ZeroDivisionError("AR1 RMSE is zero.")
                r_rmse_bistro = r_rmse(yhat, y, ar1_pred)

                result_rmse.append(
                    {
                        "START_DATE": date_start,
                        "END_DATE": date_end,
                        "NUM_VALID_VAL": len(y),
                        "HAS_NAN": has_nan,
                        "RMSE_BISTRO": round(rmse_bistro, 4),
                        "RMSE_AR1": round(rmse_ar1, 4),
                        "R_RMSE (BISTRO / AR1)": round(r_rmse_bistro, 4),
                    }
                )
            except (ValueError, ZeroDivisionError) as e:
                logger.info(
                    "Skipping AR1 metrics: idx=%s start=%s end=%s error=%s",
                    idx,
                    date_start,
                    date_end,
                    str(e),
                )
                result_rmse.append(
                    {
                        "START_DATE": date_start,
                        "END_DATE": date_end,
                        "NUM_VALID_VAL": len(y),
                        "HAS_NAN": has_nan,
                        "RMSE_BISTRO": round(rmse_bistro, 4),
                        "RMSE_AR1": None,
                        "R_RMSE (BISTRO / AR1)": None,
                    }
                )
        except Exception as e:
            logger.warning(
                "Skipping RMSE window due to unexpected error: idx=%s error=%s",
                idx,
                str(e),
            )
            continue

    df_rmse = pd.DataFrame(result_rmse)
    return df_rmse
