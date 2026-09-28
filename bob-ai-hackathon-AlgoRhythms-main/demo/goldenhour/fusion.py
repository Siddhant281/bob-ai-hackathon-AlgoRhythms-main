# fusion.py
# Placeholder for data fusion / aggregation utilities.

import pandas as pd

import storage


def cases_as_dataframe() -> pd.DataFrame:
    """Return all cases from storage as a DataFrame for use with fuse_datasets."""
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
                "lat": ls.get("lat"),
                "lon": ls.get("lon"),
                "date": ls.get("date", ""),
            }
        )
    return pd.DataFrame(rows)


def fuse_datasets(*dataframes: pd.DataFrame) -> pd.DataFrame:
    """Concatenate and deduplicate multiple incident DataFrames."""
    if not dataframes:
        return pd.DataFrame()
    combined = pd.concat(dataframes, ignore_index=True)
    return combined.drop_duplicates(subset=["incident_id"]).reset_index(drop=True)
