# storage.py
# Persistent storage for missing-person cases.
# Cases are kept in data/cases.json relative to this module's directory.

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent
_DATA_DIR = _HERE / "data"
_CASES_FILE = _DATA_DIR / "cases.json"
_LEGACY_FILE = _DATA_DIR / "case.json"

# ---------------------------------------------------------------------------
# Required field sets (used during validation)
# ---------------------------------------------------------------------------

_REQUIRED_TOP = {"status", "person", "last_seen", "reported_by", "contact"}
_REQUIRED_PERSON = {"name", "age", "gender", "height_cm", "clothing", "distinguishing_marks"}
_REQUIRED_LAST_SEEN = {"place", "date", "time"}
_VALID_STATUSES = {"Open", "Found", "Closed"}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _next_case_id(cases: list[dict]) -> str:
    """Return the next sequential case ID (MP-001, MP-002, …)."""
    numbers = []
    for c in cases:
        m = re.match(r"MP-(\d+)$", c.get("case_id", ""))
        if m:
            numbers.append(int(m.group(1)))
    nxt = max(numbers, default=0) + 1
    return f"MP-{nxt:03d}"


def _parse_date(value: str, field: str) -> None:
    """Raise ValueError if *value* is not a valid ISO date (YYYY-MM-DD)."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except (ValueError, TypeError):
        raise ValueError(f"'{field}' must be a valid date in YYYY-MM-DD format, got: {value!r}")


def _parse_time(value: str, field: str) -> None:
    """Raise ValueError if *value* is not a valid HH:MM or HH:MM:SS time string."""
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            datetime.strptime(value, fmt)
            return
        except (ValueError, TypeError):
            pass
    raise ValueError(f"'{field}' must be a valid time in HH:MM or HH:MM:SS format, got: {value!r}")


def _ensure_not_future(last_seen: dict) -> None:
    """Raise ValueError if the last-seen datetime is in the future."""
    date_str = last_seen.get("date", "")
    time_str = last_seen.get("time", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", fmt)
            # Compare as naive UTC-equivalent; use local wall-clock comparison.
            if dt > datetime.now():
                raise ValueError(
                    f"last_seen datetime {date_str} {time_str} is in the future."
                )
            return
        except ValueError as exc:
            # Re-raise only the future-date error, not a parse error.
            if "future" in str(exc):
                raise
    # If we couldn't parse at all, the earlier validators already caught it.


def _validate_case(case: dict) -> None:
    """
    Validate a case dict.  Raises ValueError with a descriptive message on
    the first problem found.
    """
    # Top-level required fields
    missing_top = _REQUIRED_TOP - case.keys()
    if missing_top:
        raise ValueError(f"Case is missing required fields: {', '.join(sorted(missing_top))}")

    # Status
    status = case.get("status")
    if status not in _VALID_STATUSES:
        raise ValueError(
            f"'status' must be one of {sorted(_VALID_STATUSES)}, got: {status!r}"
        )

    # Person sub-document
    person = case.get("person")
    if not isinstance(person, dict):
        raise ValueError("'person' must be an object.")
    missing_person = _REQUIRED_PERSON - person.keys()
    if missing_person:
        raise ValueError(
            f"'person' is missing required fields: {', '.join(sorted(missing_person))}"
        )
    if not isinstance(person.get("age"), int) or person["age"] < 0:
        raise ValueError("'person.age' must be a non-negative integer.")
    if not isinstance(person.get("height_cm"), (int, float)) or person["height_cm"] <= 0:
        raise ValueError("'person.height_cm' must be a positive number.")

    # last_seen sub-document
    last_seen = case.get("last_seen")
    if not isinstance(last_seen, dict):
        raise ValueError("'last_seen' must be an object.")
    missing_ls = _REQUIRED_LAST_SEEN - last_seen.keys()
    if missing_ls:
        raise ValueError(
            f"'last_seen' is missing required fields: {', '.join(sorted(missing_ls))}"
        )
    _parse_date(last_seen["date"], "last_seen.date")
    _parse_time(last_seen["time"], "last_seen.time")
    _ensure_not_future(last_seen)

    # Contact
    if not isinstance(case.get("contact"), str) or not case["contact"].strip():
        raise ValueError("'contact' must be a non-empty string.")

    # reported_by
    if not isinstance(case.get("reported_by"), str) or not case["reported_by"].strip():
        raise ValueError("'reported_by' must be a non-empty string.")


# ---------------------------------------------------------------------------
# Bootstrap: migrate legacy single-case file if needed
# ---------------------------------------------------------------------------


def _bootstrap() -> None:
    """Create data/cases.json from data/case.json when it does not exist yet."""
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if _CASES_FILE.exists():
        return  # Already migrated or freshly created.

    if _LEGACY_FILE.exists():
        with _LEGACY_FILE.open(encoding="utf-8") as fh:
            legacy = json.load(fh)
        # If it is already a list, use as-is; otherwise wrap it.
        cases = legacy if isinstance(legacy, list) else [legacy]
        # Ensure each case has a case_id.
        for i, c in enumerate(cases):
            if "case_id" not in c:
                c["case_id"] = f"MP-{i + 1:03d}"
        _write_raw(cases)
    else:
        # No legacy file — start with an empty list.
        _write_raw([])


def _write_raw(cases: list[dict]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with _CASES_FILE.open("w", encoding="utf-8") as fh:
        json.dump(cases, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_cases() -> list[dict]:
    """Return all cases as a list of dicts."""
    _bootstrap()
    with _CASES_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def get_case(case_id: str) -> dict | None:
    """Return a single case by ID, or None if not found."""
    for case in load_cases():
        if case.get("case_id") == case_id:
            return case
    return None


def add_case(case: dict) -> dict:
    """
    Validate *case*, assign a new case_id and created_at, persist it, and
    return the stored case.  Raises ValueError on validation failure.
    """
    # Work on a copy so the caller's dict is not mutated.
    case = dict(case)
    cases = load_cases()

    # Assign auto fields before validation so the caller can omit them.
    case.setdefault("case_id", _next_case_id(cases))
    case.setdefault("created_at", datetime.now().isoformat(timespec="seconds"))
    case.setdefault("tips", [])
    case.setdefault("cctv_sightings", [])

    _validate_case(case)

    cases.append(case)
    _write_raw(cases)
    return case


def update_case(case: dict) -> dict:
    """
    Replace an existing case (matched by case_id) with the new *case* dict.
    Raises ValueError on validation failure or if the case_id does not exist.
    """
    case = dict(case)
    case_id = case.get("case_id")
    if not case_id:
        raise ValueError("'case_id' is required for update_case().")

    cases = load_cases()
    indices = [i for i, c in enumerate(cases) if c.get("case_id") == case_id]
    if not indices:
        raise ValueError(f"No case found with case_id={case_id!r}.")

    _validate_case(case)

    cases[indices[0]] = case
    _write_raw(cases)
    return case


def add_tip(case_id: str, tip: Any) -> dict:
    """
    Append *tip* to the tips list of the given case and return the updated case.
    Raises ValueError if the case does not exist or tip is empty/None.
    """
    if tip is None or (isinstance(tip, str) and not tip.strip()):
        raise ValueError("'tip' must not be empty.")

    case = get_case(case_id)
    if case is None:
        raise ValueError(f"No case found with case_id={case_id!r}.")

    case = dict(case)
    case["tips"] = list(case.get("tips", []))
    case["tips"].append(tip)
    return update_case(case)


def add_sighting(case_id: str, sighting: Any) -> dict:
    """
    Append *sighting* to the cctv_sightings list of the given case and return
    the updated case.  Raises ValueError if the case does not exist or the
    sighting is empty/None.
    """
    if sighting is None or (isinstance(sighting, str) and not sighting.strip()):
        raise ValueError("'sighting' must not be empty.")

    case = get_case(case_id)
    if case is None:
        raise ValueError(f"No case found with case_id={case_id!r}.")

    case = dict(case)
    case["cctv_sightings"] = list(case.get("cctv_sightings", []))
    case["cctv_sightings"].append(sighting)
    return update_case(case)
