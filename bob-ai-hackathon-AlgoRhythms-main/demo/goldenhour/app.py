import sys
from pathlib import Path

# Make the goldenhour package importable when running from the repo root.
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
from datetime import datetime, date, time as dtime

import storage
import ranking
import mockdata
import crime_validation
import prevention

# ---------------------------------------------------------------------------
# Constants shared across tabs
# ---------------------------------------------------------------------------

_LOCATIONS = [
    "Northfield Park — boating lake",
    "Northfield Park — main entrance",
    "Central Station — concourse",
    "Central Station — platform 3",
    "Riverside Walk — north end",
    "Riverside Walk — south end",
    "Market Square",
    "Old Library",
    "Bus Terminal — bay 7",
    "Greenway Cycle Path — grid A4",
    "Greenway Cycle Path — grid B2",
    "Shopping Centre — level 1",
    "Shopping Centre — car park",
    "University Campus — main gate",
    "Other (describe in place field)",
]

_GENDERS = ["Male", "Female", "Non-binary", "Prefer not to say"]
_TRAVEL_MODES = ["Unknown", "On foot", "Bicycle", "Bus"]

# Session-state key for the active crime dataset
_DS_KEY = "crime_dataset"

# Session-state key for the cases version counter.
# Incremented after every storage write so every downstream read (selectboxes,
# lead ranking, zone stats, fused map, SHO brief) gets fresh data without
# needing st.cache_data at all — Streamlit re-executes the full script on
# st.rerun(), and a changed key forces widgets to re-evaluate their options.
_CV_KEY = "cases_version"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Golden Hour", layout="wide")
st.title("\U0001f691 Golden Hour")

tab_prevention, tab_search, tab_sho, tab_cases, tab_new = st.tabs(
    ["Prevention", "Search", "SHO Brief", "Cases", "New Case"]
)

# ===========================================================================
# PREVENTION TAB
# ===========================================================================

with tab_prevention:
    st.header("Prevention")

    # ── Initialise session state ─────────────────────────────────────────────
    if _DS_KEY not in st.session_state:
        st.session_state[_DS_KEY] = mockdata.get_mock_incidents()
    if _CV_KEY not in st.session_state:
        st.session_state[_CV_KEY] = 0

    active_df: pd.DataFrame = st.session_state[_DS_KEY]

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Crime data")

        st.caption(
            "Upload a CSV to replace the demo dataset. "
            "Required columns: **date**, **hour**, **crime_type**, "
            "and either **cell_id** or **lat + lon**."
        )

        uploaded = st.file_uploader(
            "Upload crime records CSV",
            type=["csv"],
            key="crime_csv_upload",
            label_visibility="collapsed",
        )

        # ── Parse and validate on upload ─────────────────────────────────────
        if uploaded is not None:
            raw = uploaded.read()
            result = crime_validation.validate_crime_csv(raw, uploaded.name)

            if result.warnings:
                for w in result.warnings:
                    st.warning(w)

            if not result.ok:
                st.error(
                    f"**{len(result.errors)} error(s) found — "
                    "fix the file before using it.**"
                )
                for err in result.errors:
                    st.error(err)
            else:
                # Show preview and summary
                preview_df = result.df.head(10)
                summary = crime_validation.summarise(result.df)

                st.success(
                    f"File valid: **{summary['total_records']} records**, "
                    f"{summary['date_min']} to {summary['date_max']}."
                )

                st.subheader("Preview (first 10 rows)")
                st.dataframe(preview_df, use_container_width=True, hide_index=True)

                st.subheader("Incidents by crime type")
                by_type = summary["by_crime_type"].reset_index()
                by_type.columns = ["Crime type", "Count"]
                st.dataframe(by_type, use_container_width=True, hide_index=True)

                col_use, col_reset = st.columns(2)
                with col_use:
                    if st.button("Use this data", type="primary", use_container_width=True):
                        st.session_state[_DS_KEY] = result.df.copy()
                        st.success("Dataset updated.")
                        st.rerun()
                with col_reset:
                    if st.button("Reset to demo data", use_container_width=True):
                        st.session_state[_DS_KEY] = mockdata.get_mock_incidents()
                        st.success("Reset to demo data.")
                        st.rerun()
        else:
            # No file uploaded — offer the reset button alone
            if st.button("Reset to demo data", use_container_width=True):
                st.session_state[_DS_KEY] = mockdata.get_mock_incidents()
                st.rerun()

    # ── Main area ─────────────────────────────────────────────────────────────
    has_latlon = "lat" in active_df.columns and "lon" in active_df.columns
    map_df = active_df.dropna(subset=["lat", "lon"]) if has_latlon else pd.DataFrame()

    if active_df.empty:
        st.info("No data loaded.")
    else:
        total = len(active_df)
        src = (
            "uploaded CSV"
            if "incident_id" not in active_df.columns
            or not active_df["incident_id"].iloc[0].startswith("INC-")
            else "demo data"
        )
        data_as_of_str = prevention.data_as_of(active_df)
        st.caption(
            f"Active dataset: **{total:,} records** ({src}) \u2014 "
            f"Data as of **{data_as_of_str}**"
        )

        if map_df.empty:
            st.warning("No lat/lon columns — hotspot map not available.")

        # ── Summary metrics ──────────────────────────────────────────────────
        m1, m2, m3 = st.columns(3)
        m1.metric("Total incidents", f"{total:,}")
        if "crime_type" in active_df.columns:
            top_type = active_df["crime_type"].value_counts().idxmax()
            m2.metric("Most common type", top_type)
        if "date" in active_df.columns:
            dates_s = pd.to_datetime(active_df["date"], errors="coerce").dropna()
            if not dates_s.empty:
                m3.metric(
                    "Date range",
                    f"{dates_s.min().date()} \u2192 {dates_s.max().date()}",
                )

        st.divider()

        # ── Top-5 zone risk cards ────────────────────────────────────────────
        st.subheader("Top-5 zones by relative risk index")
        st.caption(
            "\u26a0\ufe0f Scores are a **relative risk index** \u2014 "
            "they rank zones against each other and are **not probabilities**."
        )

        zones = prevention.zone_stats(active_df)
        top5 = zones[:5]

        if not top5:
            st.info("Not enough data to compute zone statistics.")
        else:
            for z in top5:
                trend_arrow = {
                    "up": "\u2197\ufe0f",
                    "down": "\u2198\ufe0f",
                    "flat": "\u27a1\ufe0f",
                    "insufficient data": "\u2754",
                }[z["trend_label"]]
                trend_str = (
                    f"{trend_arrow} {z['trend_pct']:+.1f}% vs prev 4 weeks"
                    if z["trend_label"] != "insufficient data"
                    else f"{trend_arrow} insufficient data for trend"
                )

                with st.container(border=True):
                    hcol, scol = st.columns([3, 1])
                    with hcol:
                        st.markdown(f"**Zone {z['zone']}**")
                        st.caption(
                            f"{z['incident_count']} incidents \u2022 "
                            f"{z['date_min']} to {z['date_max']} \u2022 "
                            f"Peak: {z['peak_day']} {z['peak_hour']:02d}:xx"
                        )
                        st.caption(trend_str)
                    with scol:
                        st.metric(
                            "Relative risk index",
                            f"{z['risk_index']:.1f} / 100",
                        )

                    with st.expander("Why this score?"):
                        c = z["_components"]
                        st.markdown(
                            f"| Component | Value |\n"
                            f"|---|---|\n"
                            f"| Recency-weighted incidents | **{c['weighted_count']:.2f}** "
                            f"(half-life = {c['half_life_days']} days) |\n"
                            f"| Day/hour pattern multiplier | **\u00d7{c['day_hour_multiplier']:.2f}** |\n"
                            f"| Event / cluster multiplier | **\u00d7{c['event_multiplier']:.2f}** |\n"
                            f"| Raw score (product) | **{c['risk_raw']:.3f}** |\n"
                            f"| Relative risk index (normalised) | **{c['risk_index']:.1f} / 100** |"
                        )
                        st.caption(z["day_hour_note"])
                        st.caption(z["event_note"])
                        st.caption(
                            f"Records used for this zone: **{z['records_used']}** "
                            f"of {total:,} total"
                        )

        st.divider()

        # ── Hotspot map ──────────────────────────────────────────────────────
        if not map_df.empty:
            st.subheader(f"Incident hotspot map ({len(map_df):,} records with coordinates)")
            display_map = map_df.copy()
            if "incident_id" not in display_map.columns:
                display_map["incident_id"] = [f"R{i+1}" for i in range(len(display_map))]
            if "severity" not in display_map.columns:
                display_map["severity"] = display_map.get(
                    "crime_type", pd.Series(["\u2014"] * len(display_map))
                )
            try:
                import hotspot
                hotspot.render_hotspot_map(display_map)
            except Exception as exc:
                st.info(f"Map unavailable in this environment: {exc}")

        # ── Crime-type breakdown ─────────────────────────────────────────────
        if "crime_type" in active_df.columns:
            st.subheader(f"Breakdown by crime type ({total:,} records)")
            breakdown = (
                active_df["crime_type"]
                .value_counts()
                .rename_axis("Crime type")
                .reset_index(name="Count")
            )
            st.dataframe(breakdown, use_container_width=True, hide_index=True)


# ===========================================================================
# Helper: ranked-leads rendering  (uses rank_leads rows directly)
# ===========================================================================

def _fmt_elapsed(minutes: float | None) -> str:
    """Format an elapsed time in minutes to a human-readable string."""
    if minutes is None:
        return "\u2014"
    if minutes < 60:
        return f"{minutes:.0f} min"
    hours = minutes / 60.0
    return f"{hours:.1f} h ({minutes:.0f} min)"


def _fmt_km(km: float | None) -> str:
    if km is None:
        return "\u2014"
    return f"{km:.2f} km"


def _render_leads(rows: list[dict]) -> None:
    """Render ranked leads as expandable cards with full traceability."""
    if not rows:
        st.info("No tips or sightings recorded yet for this case.")
        return

    st.caption(
        "\u26a0\ufe0f Scores are a **relative search priority** \u2014 "
        "they rank leads against each other and are **not probabilities**."
    )

    for i, r in enumerate(rows, 1):
        sc = r["_score_components"]
        fd = r["_feasibility_detail"]
        is_tip = r["kind"] == "Tip"
        feasible_icon = "\u2713" if r["feasible"] else "\u2717"
        feasible_word = "Feasible" if r["feasible"] else "Infeasible"

        timestamp = f"{r.get('date', '\u2014')} {r.get('time', '\u2014')}".strip()
        location = r.get("place", r.get("camera_location", "\u2014"))

        if is_tip:
            source = r.get("source", "\u2014")
            credibility = r.get("confidence", "\u2014")
            detail_text = r.get("what_seen", "\u2014")
            kind_label = "Tip"
        else:
            source = "CCTV"
            credibility = f"{r.get('match_confidence', '\u2014')}% match confidence"
            detail_text = r.get("description", "\u2014")
            kind_label = "CCTV"

        header = (
            f"#{i} \u2014 **{kind_label}** \u2014 {timestamp} \u2014 {location} "
            f"\u2014 Priority: **{r['score']:.1f} / 100** \u2014 {feasible_icon} {feasible_word}"
        )

        with st.expander(header, expanded=(i == 1)):
            col_a, col_b = st.columns(2)

            with col_a:
                st.markdown("**Lead details**")
                st.markdown(
                    f"- **Kind:** {kind_label}  \n"
                    f"- **Source:** {source}  \n"
                    f"- **Timestamp:** {timestamp}  \n"
                    f"- **Location:** {location}  \n"
                    f"- **Credibility / confidence:** {credibility}  \n"
                    f"- **Description:** {detail_text}"
                )

            with col_b:
                st.markdown("**Relative search priority components**")
                base_label = (
                    f"Confidence ({r.get('confidence', '\u2014')})"
                    if is_tip
                    else f"Match confidence \u00d7 0.9"
                )
                src_bonus_row = (
                    f"- Source bonus ({source}): **+{sc['source_bonus']:.1f}**  \n"
                    if is_tip
                    else ""
                )
                hours_ago_str = (
                    f"{sc['hours_ago']:.1f} h ago"
                    if sc["hours_ago"] is not None
                    else "unknown age"
                )
                cap_note = " (capped at 100)" if sc["capped"] else ""
                st.markdown(
                    f"- {base_label}: **{sc['base_score']:.1f}**  \n"
                    f"{src_bonus_row}"
                    f"- Recency bonus ({hours_ago_str}): **+{sc['recency_bonus']:.1f}**  \n"
                    f"- Raw total: **{sc['raw_total']:.1f}**{cap_note}  \n"
                    f"- **Relative search priority: {r['score']:.1f} / 100**"
                )
                st.caption(
                    "Not a probability. Ranks leads relative to each other only."
                )

            st.markdown("**Feasibility check**")
            if fd.get("elapsed_minutes") is None:
                st.caption(f"{feasible_icon} {r['feasibility']}")
            else:
                elapsed_str = _fmt_elapsed(fd["elapsed_minutes"])
                straight_str = _fmt_km(fd.get("straight_km"))
                travel_str = _fmt_km(fd.get("travel_km"))
                max_str = _fmt_km(fd.get("max_reachable_km"))
                speed = fd.get("max_speed_kmh")
                mode = fd.get("mode", "\u2014")
                st.markdown(
                    f"- **Time gap:** {elapsed_str}  \n"
                    f"- **Straight-line distance:** {straight_str}  \n"
                    f"- **Estimated travel distance** (\u00d71.3 detour factor): {travel_str}  \n"
                    f"- **Max reachable** ({speed} km/h {mode}): {max_str}  \n"
                    f"- **Result:** {feasible_icon} {r['feasibility']}"
                )


# ===========================================================================
# SEARCH TAB
# ===========================================================================

with tab_search:
    st.header("Search")

    # Always read fresh from disk — st.rerun() after every write ensures this
    # script re-executes, so load_cases() here always reflects the latest file.
    all_cases = storage.load_cases()
    if not all_cases:
        st.info("No cases on record. Register one in the **New Case** tab.")
    else:
        # ── Case selector ────────────────────────────────────────────────────
        def _case_label(c: dict) -> str:
            name = c.get("person", {}).get("name", "Unknown")
            return f"{c['case_id']} \u2014 {name} ({c.get('status', '?')})"

        case_labels = [_case_label(c) for c in all_cases]

        # Embed the version counter in the key so Streamlit re-evaluates the
        # widget's options list whenever a write increments _CV_KEY.
        cv = st.session_state.get(_CV_KEY, 0)
        chosen_label = st.selectbox(
            "Select case", case_labels,
            key=f"search_case_selector_{cv}",
        )
        # Re-read the selected case fresh from disk — not from the case_map
        # built above — so tips/sightings added this run are always visible.
        sel_id = next(
            c["case_id"] for c in all_cases
            if _case_label(c) == chosen_label
        )
        sel_case = storage.get_case(sel_id) or {}

        ls = sel_case.get("last_seen", {})
        st.caption(
            f"Last seen: **{ls.get('place', '\u2014')}** on {ls.get('date', '\u2014')} "
            f"at {ls.get('time', '\u2014')} | Travel mode: "
            f"{ls.get('travel_mode', 'unknown')} | "
            f"Status: **{sel_case.get('status', '\u2014')}**"
        )

        st.divider()

        col_tip, col_cctv = st.columns(2, gap="large")

        # ── Form 1: Add tip ──────────────────────────────────────────────────
        with col_tip:
            st.subheader("Add tip")
            with st.form("add_tip_form", clear_on_submit=True):
                tip_source = st.selectbox(
                    "Source", ["Public", "Family", "Informer", "Helpline"]
                )
                tip_what = st.text_area(
                    "What was seen *",
                    placeholder="Describe what was observed\u2026",
                )
                tip_place = st.selectbox("Where", _LOCATIONS)
                tip_date = st.date_input("Date", value=date.today(), key="tip_date")
                tip_time = st.time_input("Time", value=dtime(12, 0), key="tip_time")
                tip_confidence = st.selectbox(
                    "Self-reported confidence", ["Low", "Medium", "High"]
                )
                tip_submitted = st.form_submit_button("Save tip")

            if tip_submitted:
                tip_errors = []
                if not tip_what.strip():
                    tip_errors.append("'What was seen' is required.")
                tip_dt = datetime.combine(tip_date, tip_time)
                if tip_dt > datetime.now():
                    tip_errors.append(
                        f"Tip time ({tip_dt.strftime('%Y-%m-%d %H:%M')}) "
                        "cannot be in the future."
                    )
                if tip_errors:
                    for e in tip_errors:
                        st.error(e)
                else:
                    tip_obj = {
                        "source": tip_source,
                        "what_seen": tip_what.strip(),
                        "place": tip_place,
                        "lat": None,
                        "lon": None,
                        "date": tip_date.isoformat(),
                        "time": tip_time.strftime("%H:%M"),
                        "confidence": tip_confidence,
                    }
                    try:
                        storage.add_tip(sel_id, tip_obj)
                        st.session_state[_CV_KEY] = st.session_state.get(_CV_KEY, 0) + 1
                        st.success("Tip saved.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(f"Storage error: {exc}")

        # ── Form 2: Add CCTV sighting ────────────────────────────────────────
        with col_cctv:
            st.subheader("Add CCTV sighting")
            with st.form("add_sighting_form", clear_on_submit=True):
                cam_location = st.selectbox("Camera location", _LOCATIONS, key="cam_loc")
                sighting_date = st.date_input(
                    "Date", value=date.today(), key="sighting_date"
                )
                sighting_time = st.time_input(
                    "Time", value=dtime(12, 0), key="sighting_time"
                )
                sighting_desc = st.text_area(
                    "Description *",
                    placeholder="What does the footage show?",
                )
                match_conf = st.slider(
                    "Match confidence (%)", min_value=0, max_value=100, value=50
                )
                sighting_submitted = st.form_submit_button("Save sighting")

            if sighting_submitted:
                sighting_errors = []
                if not sighting_desc.strip():
                    sighting_errors.append("Description is required.")
                sig_dt = datetime.combine(sighting_date, sighting_time)
                if sig_dt > datetime.now():
                    sighting_errors.append(
                        f"Sighting time ({sig_dt.strftime('%Y-%m-%d %H:%M')}) "
                        "cannot be in the future."
                    )
                if sighting_errors:
                    for e in sighting_errors:
                        st.error(e)
                else:
                    sighting_obj = {
                        "camera_location": cam_location,
                        "lat": None,
                        "lon": None,
                        "date": sighting_date.isoformat(),
                        "time": sighting_time.strftime("%H:%M"),
                        "description": sighting_desc.strip(),
                        "match_confidence": match_conf,
                    }
                    try:
                        storage.add_sighting(sel_id, sighting_obj)
                        st.session_state[_CV_KEY] = st.session_state.get(_CV_KEY, 0) + 1
                        st.success("Sighting saved.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(f"Storage error: {exc}")

        # ── Last-seen search map ──────────────────────────────────────────────
        # sel_case is already the freshest read from disk (done at selectbox time).
        st.divider()
        st.subheader("Last-seen locations \u2014 all cases")
        import search as _search_mod
        cases_df = _search_mod.cases_as_dataframe()  # reads storage.load_cases() fresh
        map_cases = cases_df.dropna(subset=["lat", "lon"])
        if map_cases.empty:
            st.info("No cases have lat/lon coordinates \u2014 map not available.")
        else:
            try:
                import hotspot as _hotspot_mod
                _hotspot_mod.render_hotspot_map(map_cases)
            except Exception as _exc:
                st.info(f"Map unavailable in this environment: {_exc}")
        st.caption(
            f"{len(cases_df)} case(s) total \u2022 "
            f"{len(map_cases)} with coordinates shown on map"
        )

        # ── Ranked leads ─────────────────────────────────────────────────────
        # sel_case is already fresh — no second get_case() needed.
        st.divider()
        lead_rows = ranking.rank_leads(sel_case)
        n_leads = len(lead_rows)
        data_as_of_leads = sel_case.get("created_at", "\u2014")[:10]
        st.subheader(
            f"Ranked leads \u2014 tips & sightings "
            f"({n_leads} lead{'s' if n_leads != 1 else ''} \u2022 case created {data_as_of_leads})"
        )
        _render_leads(lead_rows)

# ===========================================================================
# SHO BRIEF TAB
# ===========================================================================

with tab_sho:
    st.header("SHO Brief")

    # All data is read fresh from disk on every script run.
    # No caching is used, so st.rerun() after any write guarantees freshness.
    import fusion as _fusion_mod
    import search as _search_mod

    _sho_cases = storage.load_cases()
    _cv_sho = st.session_state.get(_CV_KEY, 0)

    if not _sho_cases:
        st.info("No cases on record. Register one in the **New Case** tab.")
    else:
        _cases_df = _search_mod.cases_as_dataframe()  # fresh from disk
        _fusion_df = _fusion_mod.cases_as_dataframe()  # fresh from disk
        _crime_df = st.session_state.get(_DS_KEY, pd.DataFrame())

        # ── Metrics ──────────────────────────────────────────────────────────
        _open = sum(1 for c in _sho_cases if c.get("status") == "Open")
        _found = sum(1 for c in _sho_cases if c.get("status") == "Found")
        _closed = sum(1 for c in _sho_cases if c.get("status") == "Closed")
        _total_tips = sum(len(c.get("tips", [])) for c in _sho_cases)
        _total_sightings = sum(len(c.get("cctv_sightings", [])) for c in _sho_cases)

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("Open cases", _open)
        s2.metric("Found", _found)
        s3.metric("Closed", _closed)
        s4.metric("Total tips", _total_tips)
        s5.metric("CCTV sightings", _total_sightings)
        st.caption(
            f"Data as of: **{prevention.data_as_of(_crime_df)}** (crime dataset) \u2022 "
            f"Cases version: **{_cv_sho}** (increments on each write)"
        )

        st.divider()

        # ── Fused map: crime incidents + missing-person last-seen ────────────
        st.subheader("Fused map \u2014 crime incidents + missing-person locations")

        # Align schemas for fusion: both need incident_id, severity, lat, lon
        _crime_for_fusion = pd.DataFrame()
        if not _crime_df.empty and {"lat", "lon"}.issubset(_crime_df.columns):
            _cff = _crime_df.dropna(subset=["lat", "lon"]).copy()
            if "incident_id" not in _cff.columns:
                _cff["incident_id"] = [f"CR-{i}" for i in range(len(_cff))]
            if "severity" not in _cff.columns:
                _cff["severity"] = _cff.get("crime_type", pd.Series(["Crime"] * len(_cff)))
            _crime_for_fusion = _cff[["incident_id", "severity", "lat", "lon"]]

        _mp_for_fusion = pd.DataFrame()
        if not _fusion_df.empty and {"lat", "lon"}.issubset(_fusion_df.columns):
            _mff = _fusion_df.dropna(subset=["lat", "lon"]).copy()
            _mff = _mff.rename(columns={"incident_id": "incident_id"})
            if "severity" not in _mff.columns:
                _mff["severity"] = "Missing Person"
            _mp_for_fusion = _mff[["incident_id", "severity", "lat", "lon"]]

        _fused = _fusion_mod.fuse_datasets(_crime_for_fusion, _mp_for_fusion)

        if _fused.empty:
            st.info(
                "No coordinate data available for the fused map. "
                "Upload a crime CSV with lat/lon or register cases with coordinates."
            )
        else:
            try:
                import hotspot as _hotspot_mod
                _hotspot_mod.render_hotspot_map(_fused)
            except Exception as _exc:
                st.info(f"Map unavailable in this environment: {_exc}")
            st.caption(
                f"{len(_crime_for_fusion):,} crime record(s) + "
                f"{len(_mp_for_fusion)} missing-person location(s) = "
                f"{len(_fused):,} unique points shown"
            )

        st.divider()

        # ── Generated case summary document ──────────────────────────────────
        st.subheader("Case summary")
        st.caption(
            "Generated from live data \u2014 updates immediately on any write."
        )

        _summary_rows = []
        for _c in _sho_cases:
            _ls = _c.get("last_seen", {})
            _p = _c.get("person", {})
            _summary_rows.append({
                "Case ID": _c.get("case_id", "\u2014"),
                "Name": _p.get("name", "\u2014"),
                "Status": _c.get("status", "\u2014"),
                "Last seen place": _ls.get("place", "\u2014"),
                "Last seen date": _ls.get("date", "\u2014"),
                "Tips": len(_c.get("tips", [])),
                "CCTV sightings": len(_c.get("cctv_sightings", [])),
                "Reported by": _c.get("reported_by", "\u2014"),
            })
        _summary_df = pd.DataFrame(_summary_rows)
        st.dataframe(_summary_df, use_container_width=True, hide_index=True)

        # ── Top leads across all cases ────────────────────────────────────────
        st.subheader("Highest-priority leads across all cases")
        _all_leads = []
        for _c in _sho_cases:
            for _row in ranking.rank_leads(_c):
                _all_leads.append({
                    "Case": _c.get("case_id"),
                    "Kind": _row["kind"],
                    "Priority": _row["score"],
                    "When": f"{_row.get('date', '')} {_row.get('time', '')}".strip(),
                    "Where": _row.get("place", _row.get("camera_location", "\u2014")),
                    "Feasible": "\u2713" if _row["feasible"] else "\u2717",
                })
        if _all_leads:
            _all_leads_df = (
                pd.DataFrame(_all_leads)
                .sort_values("Priority", ascending=False)
                .reset_index(drop=True)
            )
            st.caption(
                "\u26a0\ufe0f Scores are **relative search priority** \u2014 not probabilities."
            )
            st.dataframe(_all_leads_df, use_container_width=True, hide_index=True)
        else:
            st.info("No tips or sightings recorded yet.")

# ===========================================================================
# CASES TAB
# ===========================================================================

with tab_cases:
    st.header("Cases")
    cases = storage.load_cases()
    if not cases:
        st.info("No cases on record.")
    else:
        case_ids = [c["case_id"] for c in cases]
        _cv_cases = st.session_state.get(_CV_KEY, 0)
        chosen_id = st.selectbox(
            "Select case", case_ids,
            key=f"cases_selector_{_cv_cases}",
        )
        chosen = next(c for c in cases if c["case_id"] == chosen_id)
        st.json(chosen)

# ===========================================================================
# NEW CASE TAB
# ===========================================================================

with tab_new:
    st.header("Register a Missing Person")

    st.warning(
        "\u26a0\ufe0f **Demo uses fictional data only. Do not enter real personal information.**"
    )

    with st.form("new_case_form", clear_on_submit=True):
        st.subheader("Person details")
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full name *", placeholder="e.g. Jordan Blake")
            age = st.number_input("Age", min_value=0, max_value=120, value=30, step=1)
            gender = st.selectbox("Gender", _GENDERS)
        with col2:
            height_cm = st.number_input(
                "Height (cm)", min_value=50, max_value=250, value=170, step=1
            )
            clothing = st.text_area(
                "Clothing description",
                placeholder="e.g. Blue denim jacket, white t-shirt",
            )
            marks = st.text_area(
                "Distinguishing marks",
                placeholder="e.g. Tattoo on left wrist",
            )

        st.subheader("Last seen")
        col3, col4 = st.columns(2)
        with col3:
            place_choice = st.selectbox("Location", _LOCATIONS)
            last_seen_date = st.date_input("Date *", value=date.today())
        with col4:
            last_seen_time = st.time_input("Time *", value=dtime(8, 0))
            travel_mode = st.selectbox("Likely travel mode", _TRAVEL_MODES)

        st.subheader("Reporter")
        col5, col6 = st.columns(2)
        with col5:
            reporter_name = st.text_input(
                "Reporter name *", placeholder="e.g. Casey Blake"
            )
        with col6:
            reporter_rel = st.selectbox(
                "Relationship to missing person",
                ["Parent", "Sibling", "Partner", "Friend", "Colleague", "Carer", "Other"],
            )

        submitted = st.form_submit_button("Register case")

    # ── Validation and submission ─────────────────────────────────────────────
    if submitted:
        errors = []

        name_val = full_name.strip()
        if not name_val:
            errors.append("Full name is required.")

        age_val = int(age)
        if not (0 <= age_val <= 100):
            errors.append("Age must be between 0 and 100.")

        reporter_val = reporter_name.strip()
        if not reporter_val:
            errors.append("Reporter name is required.")

        ls_dt = datetime.combine(last_seen_date, last_seen_time)
        if ls_dt > datetime.now():
            errors.append(
                f"Last-seen time ({ls_dt.strftime('%Y-%m-%d %H:%M')}) cannot be in the future."
            )

        if errors:
            for err in errors:
                st.error(err)
        else:
            case = {
                "status": "Open",
                "person": {
                    "name": name_val,
                    "age": age_val,
                    "gender": gender,
                    "height_cm": int(height_cm),
                    "clothing": clothing.strip() or "Not described",
                    "distinguishing_marks": marks.strip() or "None noted",
                    "photo": None,
                },
                "last_seen": {
                    "place": place_choice,
                    "cell_id": None,
                    "lat": None,
                    "lon": None,
                    "date": last_seen_date.isoformat(),
                    "time": last_seen_time.strftime("%H:%M"),
                    "travel_mode": travel_mode,
                },
                "reported_by": f"{reporter_val} ({reporter_rel.lower()})",
                "contact": "\u2014",
            }
            try:
                saved = storage.add_case(case)
                st.session_state[_CV_KEY] = st.session_state.get(_CV_KEY, 0) + 1
                st.success(
                    f"\u2705 Case **{saved['case_id']}** registered for **{name_val}**. "
                    "Switch to the Cases tab to view it."
                )
                st.rerun()
            except ValueError as exc:
                st.error(f"Storage error: {exc}")
