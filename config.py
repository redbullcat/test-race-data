"""
config.py — static configuration: team colours, series names, data directory.
Edit this file when teams change or new series are added.
"""

import os
_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "data")
TRACKS_DIR = os.path.join(_HERE, "tracks")

# ---------------------------------------------------------------------------
# Team colours
# Keys are matched case-insensitively against the TEAM column using substring
# matching (see utils.get_team_color).  More specific keys should come first.
# ---------------------------------------------------------------------------
TEAM_COLORS: dict[str, str] = {
    # WEC Hypercar
    "Cadillac Hertz Team JOTA": "#d4af37",
    "Peugeot TotalEnergies": "#BBD64D",
    "Ferrari AF Corse": "#d62728",
    "Toyota Gazoo Racing": "#000000",
    "BMW M Team WRT": "#2426a8",
    "Porsche Penske Motorsport": "#d3d3d3",
    "Alpine Endurance Team": "#2673e2",
    "Aston Martin Thor Team": "#01655c",
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

# Series display names (maps internal folder names → sidebar labels)
SERIES_DISPLAY: dict[str, str] = {
    "WEC": "FIA WEC",
    "IMSA": "IMSA",
    "ELMS": "ELMS",
}
