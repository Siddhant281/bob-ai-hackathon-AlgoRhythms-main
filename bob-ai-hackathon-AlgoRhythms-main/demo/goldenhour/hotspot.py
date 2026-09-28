# hotspot.py
# Placeholder for hotspot mapping utilities.

import folium
from streamlit_folium import st_folium
import pandas as pd

import storage


def cases_as_dataframe() -> pd.DataFrame:
    """Return all cases from storage as a DataFrame for use with render_hotspot_map."""
    cases = storage.load_cases()
    rows = []
    for c in cases:
        ls = c.get("last_seen", {})
        rows.append(
            {
                "incident_id": c.get("case_id", ""),
                "severity": c.get("status", ""),
                "lat": ls.get("lat"),
                "lon": ls.get("lon"),
            }
        )
    return pd.DataFrame(rows).dropna(subset=["lat", "lon"])


def render_hotspot_map(incidents: pd.DataFrame) -> None:
    """Render a folium map with incident markers."""
    centre = [incidents["lat"].mean(), incidents["lon"].mean()]
    m = folium.Map(location=centre, zoom_start=11, tiles="OpenStreetMap")

    for _, row in incidents.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=6,
            color="red",
            fill=True,
            fill_opacity=0.6,
            tooltip=f"{row['incident_id']} — {row['severity']}",
        ).add_to(m)

    st_folium(m, width=700, height=450)
