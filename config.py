"""
config.py — static configuration: team colours, series names, data directory.
Edit this file when teams change or new series are added.
"""

import os

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "data")
TRACKS_DIR = os.path.join(_HERE, "tracks")

# ---------------------------------------------------------------------------
# Series — maps sidebar display name → folder name inside data/
# ---------------------------------------------------------------------------
SERIES_DISPLAY: dict[str, str] = {
    "WEC":  "FIA WEC",
    "IMSA": "IMSA",
    "ELMS": "ELMS",
}

# ---------------------------------------------------------------------------
# Session types — folder names inside data/[series]/[year]/[race]/
# The order here controls the order they appear in the sidebar.
# ---------------------------------------------------------------------------
SESSION_TYPES = ["race", "practice", "test", "qualifying"]


# ---------------------------------------------------------------------------
# Top class priority — used to auto-select the leading class when loading data.
# Lists are checked in order; the first keyword that matches any class name
# present in the data (case-insensitive substring) wins.
# ---------------------------------------------------------------------------
CLASS_PRIORITY: dict[str, list[str]] = {
    "WEC":  ["hypercar", "lmp1"],
    "IMSA": ["gtp", "dpi", "dp", "prototype"],
    "ELMS": ["lmp2"],
}
# ---------------------------------------------------------------------------
# Team colours
# Keys are matched case-insensitively against the TEAM column.
# More specific keys should come first.
# ---------------------------------------------------------------------------
TEAM_COLORS: dict[str, str] = {
    # WEC Hypercar
    "Cadillac Hertz Team JOTA": "#d4af37",
    "Peugeot TotalEnergies": "#BBD64D",
    "Ferrari AF Corse": "#d62728",
    "Toyota Gazoo Racing": "#100100",
    "BMW M Team WRT": "#2426a8",
    "Porsche Penske Motorsport": "#d3d3d3",
    "Alpine Endurance Team": "#2673e2",
    "Aston Martin Thor Team": "#01655c",
    "Toyota Racing": "#100100",
    "Genesis Magma Racing": "#EF732F",
    "Cadillac WTR": "#0E3463",
    # WEC LMGT3
    "AF Corse": "#FCE903",
    "Proton Competition": "#fcfcff",
    "WRT": "#2426a8",
    "United Autosports": "#FF8000",
    "Akkodis ASP": "#ff443b",
    "Iron Dames": "#e5017d",
    "Manthey": "#0192cf",
    "Heart of Racing": "#242c3f",
    "Racing Spirit of Leman": "#428ca8",
    "Iron Lynx": "#fefe00",
    "TF Sport": "#eaaa1d",
    # IMSA
    "Cadillac Wayne Taylor Racing": "#0E3463",
    "JDC-Miller MotorSports": "#F8D94A",
    "Acura Meyer Shank Racing w/Curb Agajanian": "#E6662C",
    "Cadillac Whelen": "#D53C35",
}
