# crime_validation.py
# Validates a CSV of crime records for use in the Prevention tab.
#
# Required columns (case-insensitive on load, normalised to lowercase):
#   date        YYYY-MM-DD
#   hour        integer 0-23
#   crime_type  one of KNOWN_CRIME_TYPES (case-insensitive)
#
# Location: at least ONE of the following must be present:
#   cell_id                  (any non-empty string)
#   lat AND lon              (both numeric, lat -90..90, lon -180..180)
#
# Optional columns are passed through unchanged.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple

import pandas as pd

# ---------------------------------------------------------------------------
# Recognised crime types  (keep in sync with mockdata.KNOWN_CRIME_TYPES)
# ---------------------------------------------------------------------------

KNOWN_CRIME_TYPES: list[str] = [
    "Theft",
    "Assault",
    "Burglary",
    "Robbery",
    "Criminal Damage",
    "Drug Offence",
    "Public Order",
    "Missing Person",
    "Vehicle Crime",
    "Other",
]

_KNOWN_LOWER: set[str] = {t.lower() for t in KNOWN_CRIME_TYPES}

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    ok: bool                          # True only when errors is empty
    errors: list[str] = field(default_factory=list)   # row-level & structural
    warnings: list[str] = field(default_factory=list) # non-fatal notices
    df: pd.DataFrame | None = None    # cleaned DataFrame when ok=True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace and lower-case all column names."""
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _check_required_columns(cols: set[str]) -> list[str]:
    """Return a list of structural error messages for missing required columns."""
    errors: list[str] = []
    mandatory = {"date", "hour", "crime_type"}
    missing = mandatory - cols
    if missing:
        errors.append(
            f"Missing required column(s): {', '.join(sorted(missing))}. "
            f"Required: date, hour, crime_type plus cell_id OR (lat and lon)."
        )
    has_cell = "cell_id" in cols
    has_latlon = "lat" in cols and "lon" in cols
    if not has_cell and not has_latlon:
        errors.append(
            "No location column(s) found. Provide either 'cell_id' or both 'lat' and 'lon'."
        )
    return errors


def _validate_rows(df: pd.DataFrame) -> tuple[list[str], pd.DataFrame]:
    """
    Validate each row.  Returns (errors, cleaned_df).
    cleaned_df has normalised dtypes; rows with errors are still included so
    the caller can show them, but the returned df is the *cleaned* version of
    valid rows only.
    """
    errors: list[str] = []
    bad_rows: set[int] = set()

    has_cell = "cell_id" in df.columns
    has_latlon = "lat" in df.columns and "lon" in df.columns

    for idx, row in df.iterrows():
        csv_row = int(idx) + 2  # +1 for 0-base, +1 for header row

        # ── date ─────────────────────────────────────────────────────────────
        date_val = str(row.get("date", "")).strip()
        if not date_val:
            errors.append(f"Row {csv_row}: 'date' is empty.")
            bad_rows.add(idx)
        else:
            parsed_ok = False
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                try:
                    datetime.strptime(date_val, fmt)
                    parsed_ok = True
                    break
                except ValueError:
                    pass
            if not parsed_ok:
                errors.append(
                    f"Row {csv_row}: invalid date {date_val!r} "
                    "(expected YYYY-MM-DD, DD/MM/YYYY, or DD-MM-YYYY)."
                )
                bad_rows.add(idx)

        # ── hour ─────────────────────────────────────────────────────────────
        try:
            hour_val = int(float(str(row.get("hour", "")).strip()))
            if not (0 <= hour_val <= 23):
                raise ValueError
        except (ValueError, TypeError):
            errors.append(
                f"Row {csv_row}: 'hour' must be an integer 0-23, "
                f"got {row.get('hour')!r}."
            )
            bad_rows.add(idx)

        # ── crime_type ────────────────────────────────────────────────────────
        ct = str(row.get("crime_type", "")).strip()
        if not ct:
            errors.append(f"Row {csv_row}: 'crime_type' is empty.")
            bad_rows.add(idx)
        elif ct.lower() not in _KNOWN_LOWER:
            errors.append(
                f"Row {csv_row}: unknown crime_type {ct!r}. "
                f"Known types: {', '.join(KNOWN_CRIME_TYPES)}."
            )
            bad_rows.add(idx)

        # ── location ──────────────────────────────────────────────────────────
        if has_cell:
            cv = str(row.get("cell_id", "")).strip()
            if not cv:
                if not has_latlon:
                    errors.append(
                        f"Row {csv_row}: 'cell_id' is empty and no lat/lon available."
                    )
                    bad_rows.add(idx)

        if has_latlon:
            lat_raw = row.get("lat")
            lon_raw = row.get("lon")
            try:
                lat_f = float(lat_raw)
                lon_f = float(lon_raw)
                if not (-90 <= lat_f <= 90):
                    errors.append(
                        f"Row {csv_row}: 'lat' {lat_f} out of range -90..90."
                    )
                    bad_rows.add(idx)
                if not (-180 <= lon_f <= 180):
                    errors.append(
                        f"Row {csv_row}: 'lon' {lon_f} out of range -180..180."
                    )
                    bad_rows.add(idx)
            except (TypeError, ValueError):
                errors.append(
                    f"Row {csv_row}: 'lat'/'lon' must be numeric, "
                    f"got lat={lat_raw!r} lon={lon_raw!r}."
                )
                bad_rows.add(idx)

    clean_df = df.drop(index=list(bad_rows)).reset_index(drop=True)

    # Normalise dtypes on the clean subset
    if not clean_df.empty:
        clean_df["hour"] = clean_df["hour"].astype(int)
        # Normalise crime_type capitalisation to match KNOWN_CRIME_TYPES
        ct_map = {t.lower(): t for t in KNOWN_CRIME_TYPES}
        clean_df["crime_type"] = clean_df["crime_type"].str.strip().str.lower().map(ct_map)
        if has_latlon:
            clean_df["lat"] = clean_df["lat"].astype(float)
            clean_df["lon"] = clean_df["lon"].astype(float)

    return errors, clean_df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_crime_csv(raw_bytes: bytes, filename: str = "") -> ValidationResult:
    """
    Parse and validate *raw_bytes* as a CSV of crime records.

    Returns a ValidationResult with:
      - ok=True and df set when there are no errors
      - ok=False and errors populated with row-numbered messages otherwise
    Warnings are set for non-fatal issues (unknown columns, partial rows).
    """
    # Parse
    try:
        import io
        df = pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as exc:
        return ValidationResult(ok=False, errors=[f"Cannot parse CSV: {exc}"])

    if df.empty:
        return ValidationResult(ok=False, errors=["The uploaded file is empty."])

    df = _normalise_columns(df)

    # Structural column check
    col_errors = _check_required_columns(set(df.columns))
    if col_errors:
        return ValidationResult(ok=False, errors=col_errors)

    # Warn about unrecognised extra columns
    expected = {"date", "hour", "crime_type", "cell_id", "lat", "lon"}
    extra = set(df.columns) - expected
    warnings: list[str] = []
    if extra:
        warnings.append(
            f"Extra column(s) ignored for validation: {', '.join(sorted(extra))}."
        )

    # Row-level validation
    row_errors, clean_df = _validate_rows(df)

    all_errors = row_errors  # structural errors already handled above

    if all_errors:
        return ValidationResult(ok=False, errors=all_errors, warnings=warnings, df=df)

    return ValidationResult(ok=True, errors=[], warnings=warnings, df=clean_df)


def summarise(df: pd.DataFrame) -> dict:
    """
    Return a summary dict for a validated crime DataFrame:
      total_records, date_min, date_max, by_crime_type (Series)
    """
    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    return {
        "total_records": len(df),
        "date_min": dates.min().date().isoformat() if not dates.empty else "—",
        "date_max": dates.max().date().isoformat() if not dates.empty else "—",
        "by_crime_type": df["crime_type"].value_counts().sort_index(),
    }
