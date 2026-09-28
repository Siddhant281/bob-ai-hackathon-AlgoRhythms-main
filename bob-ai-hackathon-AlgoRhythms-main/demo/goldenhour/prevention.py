# prevention.py
# Zone risk analysis for the Prevention tab.
#
# Risk index model
# ----------------
# For each zone (cell_id or lat/lon bucket), we compute a "relative risk index"
# that combines three observable signals from the data:
#
#   1. Recency-weighted incident count
#      Each incident is weighted by exp(-k * age_days) where k = ln(2)/14
#      (half-weight at 14 days).  This is the primary driver.
#
#   2. Day-of-week / hour-of-day match multiplier
#      If the zone's historical peak day and peak hour match today's
#      day-of-week and the current hour bracket (±2 h), we apply ×1.2.
#      Otherwise ×1.0.  This is an observable pattern, not a prediction.
#
#   3. Event multiplier
#      A simple heuristic: if ≥3 incidents occurred in the most recent
#      7-day window for the zone (above the zone's own 28-day average),
#      we flag this as a "recent cluster" and apply ×1.15.
#      The multiplier and its reason are returned so the UI can show them.
#
# The final index is the weighted count × day/hour multiplier × event multiplier.
# It is then normalised across all zones to 0–100 (max zone = 100) so that the
# numbers are relative, not absolute counts.  The UI must label them
# "relative risk index — not a probability".
#
# No values are hardcoded; everything is derived from the input DataFrame.

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_HALF_LIFE_DAYS = 14.0  # recency weight: half-weight at 14 days
_K = math.log(2) / _HALF_LIFE_DAYS

_DAY_HOUR_MULTIPLIER = 1.20   # applied when peak day+hour matches now
_CLUSTER_MULTIPLIER = 1.15    # applied when recent-7d count > 28d average


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _recency_weight(age_days: float) -> float:
    """Exponential decay weight: 1.0 at age 0, 0.5 at HALF_LIFE_DAYS."""
    return math.exp(-_K * max(age_days, 0.0))


def _parse_date(s: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _zone_col(df: pd.DataFrame) -> str:
    """Return the name of the column to use as the zone key."""
    if "cell_id" in df.columns:
        return "cell_id"
    # Fall back: bucket lat/lon to 2 dp (≈1 km grid)
    return "_latlon_zone"


def _ensure_zone(df: pd.DataFrame) -> pd.DataFrame:
    """Add a '_zone' column if cell_id is absent."""
    df = df.copy()
    if "cell_id" in df.columns:
        df["_zone"] = df["cell_id"].astype(str).str.strip()
    elif "lat" in df.columns and "lon" in df.columns:
        df["_zone"] = (
            df["lat"].round(2).astype(str) + "," + df["lon"].round(2).astype(str)
        )
    else:
        df["_zone"] = "unknown"
    return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def zone_stats(df: pd.DataFrame, reference_date: date | None = None) -> list[dict]:
    """
    Return a list of zone stat dicts, sorted by risk_index descending.

    Each dict contains:
      zone              : str   zone identifier
      incident_count    : int   total incidents in the dataset for this zone
      weighted_count    : float recency-weighted incident count
      date_min          : str   earliest incident date (YYYY-MM-DD)
      date_max          : str   latest incident date
      peak_day          : str   day-of-week with most incidents (e.g. "Monday")
      peak_hour         : int   hour 0-23 with most incidents
      day_hour_multiplier: float  1.0 or DAY_HOUR_MULTIPLIER
      day_hour_note     : str   why the multiplier was applied (or not)
      event_multiplier  : float  1.0 or CLUSTER_MULTIPLIER
      event_note        : str   why the cluster flag was set (or not)
      risk_index        : float 0–100 (relative, normalised across zones)
      trend_pct         : float % change recent 4w vs previous 4w (can be negative)
      trend_label       : str   "up", "down", "flat", or "insufficient data"
      records_used      : int   number of records that contributed to this zone's stats
    """
    if df.empty:
        return []

    today = reference_date or date.today()
    now_hour = datetime.now().hour
    now_dow = today.weekday()  # 0=Monday

    df = _ensure_zone(df)

    # Parse dates once
    df["_date_parsed"] = df["date"].apply(
        lambda v: _parse_date(str(v)) if pd.notna(v) else None
    )
    df["_age_days"] = df["_date_parsed"].apply(
        lambda d: (today - d).days if d is not None else None
    )
    df["_weight"] = df["_age_days"].apply(
        lambda a: _recency_weight(a) if a is not None else 0.0
    )

    # Day-of-week from date
    df["_dow"] = df["_date_parsed"].apply(
        lambda d: d.weekday() if d is not None else None
    )

    results: list[dict] = []

    for zone, grp in df.groupby("_zone"):
        valid = grp[grp["_date_parsed"].notna()].copy()
        if valid.empty:
            continue

        incident_count = len(valid)
        weighted_count = float(valid["_weight"].sum())
        dates_sorted = valid["_date_parsed"].sort_values()
        date_min = dates_sorted.iloc[0].isoformat()
        date_max = dates_sorted.iloc[-1].isoformat()

        # Peak day
        dow_counts = valid["_dow"].value_counts()
        peak_dow_int = int(dow_counts.idxmax()) if not dow_counts.empty else 0
        _DOW_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                      "Friday", "Saturday", "Sunday"]
        peak_day = _DOW_NAMES[peak_dow_int]

        # Peak hour
        if "hour" in valid.columns:
            hour_counts = valid["hour"].value_counts()
            peak_hour = int(hour_counts.idxmax()) if not hour_counts.empty else 0
        else:
            peak_hour = 0

        # Day/hour multiplier
        dow_match = (now_dow == peak_dow_int)
        hour_match = abs(now_hour - peak_hour) <= 2
        if dow_match and hour_match:
            day_hour_mult = _DAY_HOUR_MULTIPLIER
            day_hour_note = (
                f"Today is {_DOW_NAMES[now_dow]} and current hour {now_hour:02d}:xx "
                f"is within \u00b12 h of peak hour {peak_hour:02d}:xx "
                f"(\u00d7{_DAY_HOUR_MULTIPLIER:.2f} applied)"
            )
        else:
            day_hour_mult = 1.0
            day_hour_note = (
                f"Peak pattern: {peak_day} at {peak_hour:02d}:xx "
                f"(today is {_DOW_NAMES[now_dow]}, hour {now_hour:02d}:xx \u2014 no match)"
            )

        # Event / cluster multiplier
        cutoff_7d = today - timedelta(days=7)
        cutoff_28d = today - timedelta(days=28)
        recent_7d = valid[valid["_date_parsed"] >= cutoff_7d]
        window_28d = valid[valid["_date_parsed"] >= cutoff_28d]
        count_7d = len(recent_7d)
        # 28-day average per week = 28d count / 4
        avg_week = len(window_28d) / 4.0 if len(window_28d) > 0 else 0.0

        if count_7d >= 3 and count_7d > avg_week:
            event_mult = _CLUSTER_MULTIPLIER
            event_note = (
                f"Recent cluster: {count_7d} incidents in last 7 days "
                f"vs {avg_week:.1f} weekly average over 28 days "
                f"(\u00d7{_CLUSTER_MULTIPLIER:.2f} applied)"
            )
        else:
            event_mult = 1.0
            event_note = (
                f"{count_7d} incidents in last 7 days vs "
                f"{avg_week:.1f} weekly average over 28 days (no cluster flag)"
            )

        risk_raw = weighted_count * day_hour_mult * event_mult

        # Trend: recent 4 weeks vs previous 4 weeks
        cutoff_4w = today - timedelta(weeks=4)
        cutoff_8w = today - timedelta(weeks=8)
        recent_4w = valid[valid["_date_parsed"] >= cutoff_4w]
        prev_4w = valid[
            (valid["_date_parsed"] >= cutoff_8w) & (valid["_date_parsed"] < cutoff_4w)
        ]
        n_recent = len(recent_4w)
        n_prev = len(prev_4w)

        if n_prev == 0 and n_recent == 0:
            trend_pct = 0.0
            trend_label = "insufficient data"
        elif n_prev == 0:
            trend_pct = 100.0
            trend_label = "up"
        else:
            trend_pct = round((n_recent - n_prev) / n_prev * 100, 1)
            if trend_pct > 5:
                trend_label = "up"
            elif trend_pct < -5:
                trend_label = "down"
            else:
                trend_label = "flat"

        results.append({
            "zone": str(zone),
            "incident_count": incident_count,
            "weighted_count": round(weighted_count, 2),
            "date_min": date_min,
            "date_max": date_max,
            "peak_day": peak_day,
            "peak_hour": peak_hour,
            "day_hour_multiplier": day_hour_mult,
            "day_hour_note": day_hour_note,
            "event_multiplier": event_mult,
            "event_note": event_note,
            "risk_raw": risk_raw,
            "trend_pct": trend_pct,
            "trend_label": trend_label,
            "records_used": incident_count,
            # breakdown for expander
            "_components": {
                "weighted_count": round(weighted_count, 2),
                "day_hour_multiplier": day_hour_mult,
                "event_multiplier": event_mult,
                "risk_raw": round(risk_raw, 3),
                "half_life_days": _HALF_LIFE_DAYS,
            },
        })

    if not results:
        return []

    # Normalise risk_raw to 0-100 relative risk index
    max_raw = max(r["risk_raw"] for r in results)
    for r in results:
        r["risk_index"] = round(r["risk_raw"] / max_raw * 100, 1) if max_raw > 0 else 0.0
        r["_components"]["risk_index"] = r["risk_index"]

    results.sort(key=lambda r: -r["risk_index"])
    return results


def data_as_of(df: pd.DataFrame) -> str:
    """Return the latest date in the DataFrame as an ISO string, or '—'."""
    if "date" not in df.columns or df.empty:
        return "\u2014"
    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    if dates.empty:
        return "\u2014"
    return dates.max().date().isoformat()
