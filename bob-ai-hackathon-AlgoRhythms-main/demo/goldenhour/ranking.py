# ranking.py
# Lead ranking and physical-feasibility checks for missing-person cases.
#
# Feasibility model
# -----------------
# We don't have real GPS coords for every named location, so we use a small
# lookup table of (lat, lon) for the fictional locations defined in app.py.
# For locations not in the table, feasibility is flagged as "unknown" rather
# than failing — we never penalise the user for gaps in the reference data.
#
# Speed caps (km/h):
#   on foot  → 7   (brisk walk / slow jog)
#   bicycle  → 25
#   bus      → 40
#   unknown  → 40  (most permissive: don't reject if mode is unknown)
#
# The Haversine formula gives straight-line distance; we multiply by 1.3 to
# approximate actual travel distance on a road/path network.

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Fictional location coordinates  (extend as new places are added)
# ---------------------------------------------------------------------------

_LOCATION_COORDS: dict[str, tuple[float, float]] = {
    "Northfield Park — boating lake":      (51.5074, -0.1278),
    "Northfield Park — main entrance":     (51.5070, -0.1285),
    "Central Station — concourse":         (51.5080, -0.1200),
    "Central Station — platform 3":        (51.5078, -0.1198),
    "Riverside Walk — north end":          (51.5100, -0.1150),
    "Riverside Walk — south end":          (51.5050, -0.1140),
    "Market Square":                       (51.5090, -0.1300),
    "Old Library":                         (51.5065, -0.1320),
    "Bus Terminal — bay 7":                (51.5085, -0.1220),
    "Greenway Cycle Path — grid A4":       (51.5110, -0.1350),
    "Greenway Cycle Path — grid B2":       (51.5095, -0.1330),
    "Shopping Centre — level 1":           (51.5060, -0.1260),
    "Shopping Centre — car park":          (51.5055, -0.1255),
    "University Campus — main gate":       (51.5120, -0.1180),
}

# ---------------------------------------------------------------------------
# Speed caps per travel mode (km/h)
# ---------------------------------------------------------------------------

_MAX_SPEED: dict[str, float] = {
    "on foot":  7.0,
    "bicycle":  25.0,
    "bus":      40.0,
    "unknown":  40.0,   # most permissive
}

_DETOUR_FACTOR = 1.3  # straight-line to road-distance multiplier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return straight-line distance in km between two WGS-84 points."""
    r = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def _parse_dt(date_str: str, time_str: str) -> datetime | None:
    """Parse a date + time pair into a datetime, returning None on failure."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(f"{date_str} {time_str}", fmt)
        except ValueError:
            pass
    return None


def _coords_for(place: str | None, lat: float | None, lon: float | None) -> tuple[float, float] | None:
    """Return (lat, lon) for a place, preferring explicit coords over the lookup table."""
    if lat is not None and lon is not None:
        try:
            return (float(lat), float(lon))
        except (TypeError, ValueError):
            pass
    if place and place in _LOCATION_COORDS:
        return _LOCATION_COORDS[place]
    return None


# ---------------------------------------------------------------------------
# Public: physical feasibility
# ---------------------------------------------------------------------------


def check_feasibility(
    origin_place: str | None,
    origin_lat: float | None,
    origin_lon: float | None,
    origin_date: str,
    origin_time: str,
    lead_place: str | None,
    lead_lat: float | None,
    lead_lon: float | None,
    lead_date: str,
    lead_time: str,
    travel_mode: str = "unknown",
) -> tuple[bool, str, dict]:
    """
    Return (feasible: bool, reason: str, detail: dict).

    detail contains the raw numbers used in the check so callers can display
    them without re-computing:
      elapsed_minutes, elapsed_hours, straight_km, travel_km,
      max_reachable_km, max_speed_kmh, mode, origin_coords, lead_coords
    All values are None when the check could not be performed.

    The feasible flag and reason string are computed identically to before —
    only the extra detail dict is new.
    """
    _no_detail: dict = {
        "elapsed_minutes": None, "elapsed_hours": None,
        "straight_km": None, "travel_km": None,
        "max_reachable_km": None, "max_speed_kmh": None,
        "mode": (travel_mode or "unknown").lower(),
        "origin_coords": None, "lead_coords": None,
    }

    origin_dt = _parse_dt(origin_date, origin_time)
    lead_dt = _parse_dt(lead_date, lead_time)

    if origin_dt is None or lead_dt is None:
        return True, "Cannot check \u2014 date/time missing or unparseable", _no_detail

    if lead_dt < origin_dt:
        return False, f"Lead time {lead_date} {lead_time} is before last-seen time", _no_detail

    elapsed_hours = (lead_dt - origin_dt).total_seconds() / 3600.0
    elapsed_minutes = elapsed_hours * 60.0

    origin_coords = _coords_for(origin_place, origin_lat, origin_lon)
    lead_coords = _coords_for(lead_place, lead_lat, lead_lon)

    if origin_coords is None or lead_coords is None:
        return True, "Cannot check \u2014 location coordinates not available", {
            **_no_detail,
            "elapsed_minutes": round(elapsed_minutes, 1),
            "elapsed_hours": round(elapsed_hours, 2),
        }

    straight_km = _haversine_km(*origin_coords, *lead_coords)
    travel_km = straight_km * _DETOUR_FACTOR
    mode_key = (travel_mode or "unknown").lower()
    max_speed = _MAX_SPEED.get(mode_key, _MAX_SPEED["unknown"])
    max_reachable_km = max_speed * elapsed_hours

    detail: dict = {
        "elapsed_minutes": round(elapsed_minutes, 1),
        "elapsed_hours": round(elapsed_hours, 2),
        "straight_km": round(straight_km, 2),
        "travel_km": round(travel_km, 2),
        "max_reachable_km": round(max_reachable_km, 2),
        "max_speed_kmh": max_speed,
        "mode": mode_key,
        "origin_coords": origin_coords,
        "lead_coords": lead_coords,
    }

    if travel_km <= max_reachable_km:
        return (
            True,
            f"\u2713 {travel_km:.1f} km in {elapsed_hours:.1f} h "
            f"(max {max_reachable_km:.1f} km at {max_speed} km/h {mode_key})",
            detail,
        )
    else:
        return (
            False,
            f"\u2717 {travel_km:.1f} km in {elapsed_hours:.1f} h "
            f"exceeds {max_reachable_km:.1f} km at {max_speed} km/h {mode_key}",
            detail,
        )


# ---------------------------------------------------------------------------
# Public: rank leads for a case
# ---------------------------------------------------------------------------


def score_lead(lead: dict, kind: str) -> tuple[float, dict]:
    """
    Return (score: float 0-100, components: dict).
    Higher score is more actionable.  Scoring formulas are unchanged.

    Scoring weights
    ---------------
    Tip  : confidence Low=20, Medium=50, High=80  (base)
           source bonus: Informer +10, Family +5
    CCTV : match_confidence (0-100) is used directly as base
           then scaled by 0.9 so tips and sightings share the same scale
    Both : recency bonus (last 24 h +10, last 72 h +5)

    components keys: base_score, source_bonus, recency_bonus, hours_ago,
                     capped (bool), raw_total
    """
    components: dict = {
        "base_score": 0.0,
        "source_bonus": 0.0,
        "recency_bonus": 0.0,
        "hours_ago": None,
        "capped": False,
        "raw_total": 0.0,
    }
    score = 0.0

    if kind == "tip":
        conf_map = {"low": 20.0, "medium": 50.0, "high": 80.0}
        conf = str(lead.get("confidence", "medium")).lower()
        base = conf_map.get(conf, 50.0)
        source_bonus_map = {"informer": 10.0, "family": 5.0}
        source = str(lead.get("source", "")).lower()
        src_bonus = source_bonus_map.get(source, 0.0)
        score = base + src_bonus
        components["base_score"] = base
        components["source_bonus"] = src_bonus

    elif kind == "sighting":
        base = float(lead.get("match_confidence", 50)) * 0.9
        score = base
        components["base_score"] = base

    # Recency bonus — formula unchanged
    date_str = str(lead.get("date", ""))
    time_str = str(lead.get("time", ""))
    dt = _parse_dt(date_str, time_str)
    rec_bonus = 0.0
    if dt is not None:
        hours_ago = (datetime.now() - dt).total_seconds() / 3600.0
        components["hours_ago"] = round(hours_ago, 1)
        if hours_ago <= 24:
            rec_bonus = 10.0
        elif hours_ago <= 72:
            rec_bonus = 5.0
    score += rec_bonus
    components["recency_bonus"] = rec_bonus
    components["raw_total"] = round(score, 1)
    components["capped"] = score > 100.0

    return min(score, 100.0), components


def rank_leads(case: dict) -> list[dict]:
    """
    Return a combined, time-sorted list of tips and CCTV sightings for a case,
    each augmented with:
      - kind               : "Tip" | "CCTV"
      - score              : float 0-100
      - _score_components  : dict  (base_score, source_bonus, recency_bonus, …)
      - feasible           : bool
      - feasibility        : str   (human-readable summary)
      - _feasibility_detail: dict  (elapsed_minutes, travel_km, max_reachable_km, …)
    Sorted by score descending, then by datetime descending.
    Scoring formulas and sort order are unchanged.
    """
    last_seen = case.get("last_seen", {})
    travel_mode = last_seen.get("travel_mode", "unknown")
    origin_place = last_seen.get("place")
    origin_lat = last_seen.get("lat")
    origin_lon = last_seen.get("lon")
    origin_date = last_seen.get("date", "")
    origin_time = last_seen.get("time", "")

    rows: list[dict] = []

    for tip in case.get("tips", []):
        feasible, reason, fdetail = check_feasibility(
            origin_place, origin_lat, origin_lon, origin_date, origin_time,
            tip.get("place"), tip.get("lat"), tip.get("lon"),
            str(tip.get("date", "")), str(tip.get("time", "")),
            travel_mode,
        )
        score, components = score_lead(tip, "tip")
        rows.append({
            **tip,
            "kind": "Tip",
            "score": round(score, 1),
            "_score_components": components,
            "feasible": feasible,
            "feasibility": reason,
            "_feasibility_detail": fdetail,
        })

    for s in case.get("cctv_sightings", []):
        feasible, reason, fdetail = check_feasibility(
            origin_place, origin_lat, origin_lon, origin_date, origin_time,
            s.get("camera_location"), s.get("lat"), s.get("lon"),
            str(s.get("date", "")), str(s.get("time", "")),
            travel_mode,
        )
        score, components = score_lead(s, "sighting")
        rows.append({
            **s,
            "kind": "CCTV",
            "score": round(score, 1),
            "_score_components": components,
            "feasible": feasible,
            "feasibility": reason,
            "_feasibility_detail": fdetail,
        })

    rows.sort(key=lambda r: (
        -r["score"],
        -((_parse_dt(str(r.get("date", "")), str(r.get("time", ""))) or datetime.min).timestamp()),
    ))
    return rows
