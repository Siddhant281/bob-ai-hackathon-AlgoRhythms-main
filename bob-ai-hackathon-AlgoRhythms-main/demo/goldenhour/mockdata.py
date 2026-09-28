# mockdata.py
# Mock data generation utilities.

import pandas as pd
import numpy as np
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Crime types recognised by the application.
# Keep in sync with crime_validation.KNOWN_CRIME_TYPES.
# ---------------------------------------------------------------------------
KNOWN_CRIME_TYPES = [
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


def get_mock_incidents(n: int = 50, seed: int = 42) -> pd.DataFrame:
    """Return a DataFrame of randomly generated incident records.

    Columns
    -------
    incident_id       : str   INC-0000
    date              : str   YYYY-MM-DD  (last 90 days)
    hour              : int   0-23
    cell_id           : str   grid reference e.g. A1
    lat               : float
    lon               : float
    crime_type        : str   one of KNOWN_CRIME_TYPES
    severity          : str   Low / Medium / High / Critical
    response_time_min : int
    """
    rng = np.random.default_rng(seed)

    today = date.today()
    offsets = rng.integers(0, 90, n)
    dates = [(today - timedelta(days=int(d))).isoformat() for d in offsets]

    # 5×5 fictional grid cells A1–E5
    cols_grid = list("ABCDE")
    rows_grid = list("12345")
    cell_ids = [
        f"{cols_grid[rng.integers(0, 5)]}{rows_grid[rng.integers(0, 5)]}"
        for _ in range(n)
    ]

    return pd.DataFrame(
        {
            "incident_id": [f"INC-{i:04d}" for i in range(n)],
            "date": dates,
            "hour": rng.integers(0, 24, n).tolist(),
            "cell_id": cell_ids,
            "lat": rng.uniform(51.4, 51.6, n),
            "lon": rng.uniform(-0.2, 0.1, n),
            "crime_type": rng.choice(KNOWN_CRIME_TYPES, n).tolist(),
            "severity": rng.choice(["Low", "Medium", "High", "Critical"], n).tolist(),
            "response_time_min": rng.integers(3, 45, n).tolist(),
        }
    )
