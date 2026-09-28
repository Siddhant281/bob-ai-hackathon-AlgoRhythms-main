# search.py
# Placeholder for patient / record search utilities.

import pandas as pd

import storage


def cases_as_dataframe() -> pd.DataFrame:
    """Return all cases from storage as a DataFrame for use with search_incidents."""
    cases = storage.load_cases()
    rows = []
    for c in cases:
        person = c.get("person", {})
        ls = c.get("last_seen", {})
        rows.append(
            {
                "incident_id": c.get("case_id", ""),
                "severity": c.get("status", ""),
                "name": person.get("name", ""),
                "age": person.get("age"),
                "gender": person.get("gender", ""),
                "place": ls.get("place", ""),
                "lat": ls.get("lat"),
                "lon": ls.get("lon"),
                "date": ls.get("date", ""),
                "time": ls.get("time", ""),
                "reported_by": c.get("reported_by", ""),
            }
        )
    return pd.DataFrame(rows)


def search_incidents(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Filter incident records by a free-text query against incident_id and severity."""
    if not query:
        return df
    q = query.lower()
    mask = df["incident_id"].str.lower().str.contains(q) | df["severity"].str.lower().str.contains(q)
    return df[mask].reset_index(drop=True)
