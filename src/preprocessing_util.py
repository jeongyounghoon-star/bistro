import logging
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_yoy_inflation(series: pd.Series, *, freq: str = "M") -> pd.Series:
    """Compute year-over-year inflation (%) from a CPI level series."""
    if freq == "M":
        lag = 12
    elif freq == "Q":
        lag = 4
    else:
        lag = 12

    lagged = series.shift(lag)
    with np.errstate(divide="ignore", invalid="ignore"):
        yoy = (series.values - lagged.values) / np.abs(lagged.values) * 100
    return pd.Series(yoy, index=series.index, name=series.name)


def detect_and_impute_gaps(
    df: pd.DataFrame,
    *,
    freq: str = "M",
    tolerance_days: int = 10,
) -> pd.DataFrame:
    """Reindex a monthly/quarterly series to a full grid and interpolate missing points.

    Notes
    -----
    This assumes the index represents period-end timestamps (month-end / quarter-end).
    If timestamps are not aligned, they are snapped to their period end; a warning is
    logged if the snap exceeds `tolerance_days`.
    """
    if df.empty:
        return df

    df = df.sort_index()
    df = df.copy()

    if isinstance(df.index, pd.PeriodIndex):
        per = df.index.asfreq(freq)
        if freq == "M":
            df.index = per.to_timestamp(freq="M")
        elif freq == "Q":
            df.index = per.to_timestamp(freq="Q")
        else:
            df.index = per.to_timestamp()
    else:
        if not pd.api.types.is_datetime64_any_dtype(df.index):
            df.index = pd.to_datetime(df.index)

        per = df.index.to_period(freq=freq)
        if freq == "M":
            snapped = per.to_timestamp(freq="M")
        elif freq == "Q":
            snapped = per.to_timestamp(freq="Q")
        else:
            snapped = per.to_timestamp()

        if tolerance_days is not None and len(df.index) > 0:
            snap_diff_days = np.abs((df.index.values - snapped.values).astype("timedelta64[D]").astype(int))
            max_diff = int(np.max(snap_diff_days)) if len(snap_diff_days) else 0
            if max_diff > int(tolerance_days):
                logger.warning(
                    "Index timestamps are not aligned to %s period ends (max snap=%s days > tolerance_days=%s).",
                    freq,
                    max_diff,
                    tolerance_days,
                )

        df.index = pd.DatetimeIndex(snapped)
        df = df[~df.index.duplicated(keep="last")].sort_index()

    full_index = pd.date_range(start=df.index.min(), end=df.index.max(), freq=freq)
    if len(full_index) == len(df.index) and df.index.equals(full_index):
        return df

    df_reindexed = df.reindex(full_index)
    return df_reindexed.interpolate(method="time")


def forward_fill_to_daily(df: pd.DataFrame, *, patch_size_days: int = 32) -> pd.DataFrame:
    """Forward-fill monthly/quarterly data to daily frequency."""
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df.index):
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    start_date = df.index[0]
    end_date = df.index[-1] + pd.Timedelta(days=patch_size_days - 1)
    daily_index = pd.date_range(start=start_date, end=end_date, freq="D")
    return df.reindex(daily_index, method="ffill")


def expand_monthly_dt_to_daily_asof(df_dt: pd.DataFrame, *, patch_size_days: int = 32) -> pd.DataFrame:
    """
    Expand month-end DatetimeIndex to daily using an as-of (backward) join.

    This is useful for covariates where NaNs must be preserved (no LOCF across
    missing monthly values).
    """
    if df_dt.empty:
        return df_dt

    if int(patch_size_days) < 1:
        raise ValueError(f"patch_size_days must be >= 1, got {patch_size_days}")

    df_dt = df_dt.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_dt.index):
        df_dt.index = pd.to_datetime(df_dt.index)
    df_dt = df_dt[~df_dt.index.duplicated(keep="last")].sort_index()

    start_date = df_dt.index[0]
    end_date = df_dt.index[-1] + pd.Timedelta(days=int(patch_size_days) - 1)
    daily_index = pd.date_range(start=start_date, end=end_date, freq="D")

    left = pd.DataFrame({"ts": daily_index})
    right = df_dt.reset_index()
    right = right.rename(columns={right.columns[0]: "ts"}).sort_values("ts")

    merged = pd.merge_asof(left, right, on="ts", direction="backward")
    merged = merged.set_index("ts")
    merged.index = pd.DatetimeIndex(merged.index)
    return merged[df_dt.columns.tolist()]


def pad_future_markers(
    df: pd.DataFrame,
    *,
    target_col: str,
    n_pad_periods: int,
    freq: str = "M",
) -> pd.DataFrame:
    """Pad future periods with marker values (-1/-2) so rolling windows always have enough horizon."""
    if df.empty:
        return df

    df = df.sort_index()
    last_date = df.index[-1]
    months_step = 3 if freq == "Q" else 1

    pad_dates = [last_date + pd.DateOffset(months=i * months_step) for i in range(1, n_pad_periods + 1)]
    pad_values = [-1 if i % 2 == 0 else -2 for i in range(n_pad_periods)]
    pad_df = pd.DataFrame({target_col: pad_values}, index=pd.DatetimeIndex(pad_dates))

    out = pd.concat([df, pad_df])
    out = out[~out.index.duplicated(keep="first")].sort_index()
    return out


def _find_change_points(arr: np.ndarray) -> List[int]:
    arr = np.asarray(arr)
    if len(arr) <= 1:
        return []
    return (np.flatnonzero(arr[:-1] != arr[1:]) + 1).tolist()


def _fill_missing_jumps(change_points: List[int], arr_len: int, *, max_jump: int) -> List[int]:
    if not change_points:
        return list(range(max_jump, arr_len, max_jump))

    filled: List[int] = []
    prev_pos = 0
    for cp in change_points:
        while cp - prev_pos > max_jump:
            prev_pos += max_jump
            if prev_pos < cp:
                filled.append(prev_pos)
        filled.append(cp)
        prev_pos = cp

    while arr_len - prev_pos > max_jump:
        prev_pos += max_jump
        if prev_pos < arr_len:
            filled.append(prev_pos)

    return filled


def create_boolean_masks(arr: np.ndarray, *, steps_per_period: int) -> List[np.ndarray]:
    """Create boolean masks for each period segment in a forward-filled array."""
    arr = np.asarray(arr)
    n = len(arr)
    if n == 0:
        return []

    change_points = _find_change_points(arr)
    if not change_points:
        change_points = [0]

    change_points = _fill_missing_jumps(change_points, n, max_jump=int(steps_per_period))

    masks: List[np.ndarray] = []
    start_idx = 0
    for cp in change_points:
        mask = np.zeros(n, dtype=bool)
        mask[start_idx:cp] = True
        masks.append(mask)
        start_idx = cp

    mask = np.zeros(n, dtype=bool)
    mask[start_idx:] = True
    masks.append(mask)
    return masks


def aggregate_daily_forecast_to_monthly(
    forecast_samples: np.ndarray,
    label_target: np.ndarray,
    last_input: float | None,
    *,
    steps_per_period: int,
    expected_periods: int,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Aggregate daily forecast samples back to monthly/quarterly resolution."""
    forecast_samples = np.asarray(forecast_samples)
    if forecast_samples.ndim != 2:
        raise ValueError(f"forecast_samples must be 2D (S, H); got shape={forecast_samples.shape}")

    label_target = np.asarray(label_target)
    if label_target.ndim != 1:
        raise ValueError(f"label_target must be 1D; got shape={label_target.shape}")

    if forecast_samples.shape[1] != label_target.shape[0]:
        raise ValueError(
            "Forecast/label length mismatch: "
            f"forecast_samples.shape[1]={forecast_samples.shape[1]} vs label_target.shape[0]={label_target.shape[0]}"
        )

    masks = create_boolean_masks(label_target, steps_per_period=int(steps_per_period))

    if last_input is not None and label_target.size > 0 and float(last_input) == float(label_target[0]):
        removed_len = int(np.sum(masks[0])) if masks else 0
        masks = masks[1:] if len(masks) > 1 else []
        label_target_trimmed = label_target[removed_len:] if removed_len > 0 else label_target
    else:
        label_target_trimmed = label_target

    preds: List[float] = []
    gts: List[float] = []
    cis: List[List[float]] = []
    cumulative_idx = 0

    for mask in masks:
        if not mask.any():
            continue

        segment = forecast_samples[:, mask]
        segment_means = np.mean(segment, axis=1)

        preds.append(float(np.median(segment_means)))
        cis.append(
            [
                float(np.quantile(segment_means, 0.05)),
                float(np.quantile(segment_means, 0.95)),
            ]
        )

        seg_len = int(np.sum(mask))
        if cumulative_idx < len(label_target_trimmed):
            gts.append(float(label_target_trimmed[cumulative_idx]))
        else:
            gts.append(np.nan)
        cumulative_idx += seg_len

        if len(preds) >= expected_periods:
            break

    while len(preds) < expected_periods:
        preds.append(np.nan)
        gts.append(np.nan)
        cis.append([np.nan, np.nan])

    return np.asarray(preds), np.asarray(gts), np.asarray(cis)


def _standardize_period_index(idx, *, freq: str) -> pd.PeriodIndex:
    if isinstance(idx, pd.PeriodIndex):
        if idx.freqstr != freq:
            return idx.asfreq(freq)
        return idx

    dt = pd.to_datetime(idx)
    return dt.to_period(freq=freq)


def _period_to_period_end_timestamp(per: pd.Period) -> pd.Timestamp:
    if per.freqstr == "M":
        return per.to_timestamp(freq="M")
    if per.freqstr == "Q":
        return per.to_timestamp(freq="Q")
    return per.to_timestamp()


@dataclass(frozen=True)
class DailyInferencePrep:
    df_monthly: pd.DataFrame
    df_yoy_dt: pd.DataFrame
    daily_df: pd.DataFrame
    forecast_start: pd.Period
    train_end: pd.Period
    cutoff_date_dt: pd.Timestamp
    cutoff_period_daily: pd.Period
    pdt_steps: int
    ctx_steps: int
    dist_steps: int
    windows: int


def prepare_yoy_monthly_for_daily_inference(
    df_yoy_period: pd.DataFrame,
    *,
    target_col: str,
    freq: str,
    forecast_start_date: str,
    pdt_patches: int,
    ctx_patches: int,
    steps_per_period: int,
    rolling_windows: int,
    window_distance_patches: int,
    tolerance_days: int = 10,
) -> DailyInferencePrep:
    """Prepare an already-YoY monthly series for inference_v4-style daily Moirai inference."""
    if isinstance(df_yoy_period, pd.Series):
        df_yoy_period = df_yoy_period.to_frame(name=target_col)

    if target_col not in df_yoy_period.columns:
        raise KeyError(f"Missing target_col={target_col!r} in df_yoy_period columns={list(df_yoy_period.columns)}")

    df_monthly = df_yoy_period[[target_col]].copy()
    df_monthly.index = _standardize_period_index(df_monthly.index, freq=freq)
    df_monthly = df_monthly[~df_monthly.index.duplicated(keep="first")].sort_index()

    df_yoy_dt = df_monthly.copy()
    if freq == "M":
        df_yoy_dt.index = df_yoy_dt.index.to_timestamp(freq="M")
    elif freq == "Q":
        df_yoy_dt.index = df_yoy_dt.index.to_timestamp(freq="Q")
    else:
        df_yoy_dt.index = df_yoy_dt.index.to_timestamp()
    df_yoy_dt = detect_and_impute_gaps(df_yoy_dt.dropna(), freq=freq, tolerance_days=tolerance_days)

    forecast_start = pd.Period(forecast_start_date, freq=freq)
    train_end = forecast_start - 1
    cutoff_date_dt = _period_to_period_end_timestamp(train_end)
    cutoff_period_daily = pd.Period(cutoff_date_dt.strftime("%Y-%m-%d"))

    test_len_periods = int((df_yoy_dt.index > cutoff_date_dt).sum())
    distance_periods = int(window_distance_patches)
    max_windows = max(0, (test_len_periods - int(pdt_patches)) // distance_periods + 1)
    windows = min(int(rolling_windows), max_windows)

    padded = pad_future_markers(
        df_yoy_dt,
        target_col=target_col,
        n_pad_periods=int(pdt_patches),
        freq=freq,
    )
    daily_df = forward_fill_to_daily(padded, patch_size_days=int(steps_per_period))

    pdt_steps = int(steps_per_period) * int(pdt_patches)
    ctx_steps = int(steps_per_period) * int(ctx_patches)
    dist_steps = int(steps_per_period) * int(window_distance_patches)

    return DailyInferencePrep(
        df_monthly=df_monthly,
        df_yoy_dt=df_yoy_dt,
        daily_df=daily_df,
        forecast_start=forecast_start,
        train_end=train_end,
        cutoff_date_dt=cutoff_date_dt,
        cutoff_period_daily=cutoff_period_daily,
        pdt_steps=pdt_steps,
        ctx_steps=ctx_steps,
        dist_steps=dist_steps,
        windows=windows,
    )


@dataclass(frozen=True)
class DailyInferencePrepLongDF:
    df_monthly_target: pd.DataFrame
    df_dt: pd.DataFrame
    daily_long_df: pd.DataFrame
    forecast_start: pd.Period
    train_end: pd.Period
    cutoff_date_dt: pd.Timestamp
    cutoff_period_daily: pd.Period
    pdt_steps: int
    ctx_steps: int
    dist_steps: int
    windows: int


def prepare_long_df_monthly_for_daily_inference(
    df_long_period: pd.DataFrame,
    *,
    item_id_col: str,
    target_col: str,
    past_dynamic_real_cols: list[str],
    freq: str,
    forecast_start_date: str,
    pdt_patches: int,
    ctx_patches: int,
    steps_per_period: int,
    rolling_windows: int,
    window_distance_patches: int,
    tolerance_days: int = 10,
) -> DailyInferencePrepLongDF:
    """Prepare a monthly long dataframe (target + covariates) for daily Moirai inference."""
    missing_cols = [
        col
        for col in [item_id_col, target_col, *past_dynamic_real_cols]
        if col not in df_long_period.columns
    ]
    if missing_cols:
        raise KeyError(f"Missing columns in df_long_period: {missing_cols}")

    if len(past_dynamic_real_cols) == 0:
        raise ValueError("past_dynamic_real_cols must not be empty.")

    item_ids = df_long_period[item_id_col].dropna().unique().tolist()
    if len(item_ids) != 1:
        raise ValueError(f"Expected a single item_id, got {item_ids}")
    item_id_val = item_ids[0]

    df_long_period = df_long_period.copy()
    df_long_period.index = _standardize_period_index(df_long_period.index, freq=freq)
    df_long_period = df_long_period[~df_long_period.index.duplicated(keep="first")].sort_index()

    df_monthly_target = df_long_period[[target_col]].copy()

    df_dt = df_long_period[[target_col] + past_dynamic_real_cols].copy()
    if freq == "M":
        df_dt.index = df_dt.index.to_timestamp(freq="M")
    elif freq == "Q":
        df_dt.index = df_dt.index.to_timestamp(freq="Q")
    else:
        df_dt.index = df_dt.index.to_timestamp()

    df_dt = detect_and_impute_gaps(df_dt, freq=freq, tolerance_days=tolerance_days)

    forecast_start = pd.Period(forecast_start_date, freq=freq)
    train_end = forecast_start - 1
    cutoff_date_dt = _period_to_period_end_timestamp(train_end)
    cutoff_period_daily = pd.Period(cutoff_date_dt.strftime("%Y-%m-%d"))

    test_len_periods = int((df_dt.index > cutoff_date_dt).sum())
    distance_periods = int(window_distance_patches)
    max_windows = max(0, (test_len_periods - int(pdt_patches)) // distance_periods + 1)
    windows = min(int(rolling_windows), max_windows)

    padded = pad_future_markers(
        df_dt,
        target_col=target_col,
        n_pad_periods=int(pdt_patches),
        freq=freq,
    )
    daily_df = expand_monthly_dt_to_daily_asof(padded, patch_size_days=int(steps_per_period))

    daily_long_df = daily_df.copy()
    daily_long_df[item_id_col] = item_id_val

    pdt_steps = int(steps_per_period) * int(pdt_patches)
    ctx_steps = int(steps_per_period) * int(ctx_patches)
    dist_steps = int(steps_per_period) * int(window_distance_patches)

    return DailyInferencePrepLongDF(
        df_monthly_target=df_monthly_target,
        df_dt=df_dt,
        daily_long_df=daily_long_df,
        forecast_start=forecast_start,
        train_end=train_end,
        cutoff_date_dt=cutoff_date_dt,
        cutoff_period_daily=cutoff_period_daily,
        pdt_steps=pdt_steps,
        ctx_steps=ctx_steps,
        dist_steps=dist_steps,
        windows=windows,
    )
