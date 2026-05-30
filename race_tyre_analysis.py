"""race_tyre_analysis.py — Pit notes PDF parser for IMSA."""

import os
import re

import pandas as pd
import streamlit as st

try:
    import pdfplumber
    _PDF_OK = True
except ImportError:
    _PDF_OK = False


_PIT_PATTERN = re.compile(
    r"At\s(?P<local_time>\d{1,2}:\d{2}\s(?:am|pm))\s"
    r"\((?P<race_time>(?:\d+h\s)?\d+m)\)\s"
    r"(?P<driver>.+?)\s"
    r"\(#(?P<car_number>\d+)-(?P<class>\w+)[^\)]*\)\s"
    r"(?P<pos_type>CP|OP):\s\d+,\s?pits\.?\s"
    r"(?P<actions>"
    r"fuel(?: only|, tires?)?"
    r"(?:, driver change)?"
    r"|fuel, tires"
    r"|fuel, tires, driver change"
    r"|fuel only"
    r")\.?"
    r"(?:\sDC:\s(?P<driver_change>[^\.]+))?\.?\s"
    r"Pit Lane:\s(?P<pit_time>\d{2}:\d{2})",
    re.IGNORECASE,
)


@st.cache_data(show_spinner="Parsing pit notes PDF…")
def _parse_pitnotes(pdf_path: str) -> pd.DataFrame:
    if not _PDF_OK:
        return pd.DataFrame()

    with pdfplumber.open(pdf_path) as pdf:
        lines = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                for line in text.split("\n"):
                    if re.search(r"\bpits\b", line.lower()):
                        lines.append((line, i + 1))

    records = []
    for line, page_num in lines:
        m = _PIT_PATTERN.search(line)
        if not m:
            continue
        d = m.groupdict()
        actions = d["actions"].lower()
        records.append({
            "Local Time": d["local_time"],
            "Race Time": d["race_time"],
            "Car": d["car_number"],
            "Class": d["class"],
            "Driver Out": d["driver"].strip(),
            "Driver In": d["driver_change"].strip() if d["driver_change"] else d["driver"].strip(),
            "Pos Type": d["pos_type"],
            "Fuel only": "fuel only" in actions,
            "Fuel + tyres": "fuel, tires" in actions or "fuel, tyre" in actions,
            "Driver Change": bool(d["driver_change"]) or "driver change" in actions,
            "Pit Lane Time": d["pit_time"],
            "Page": page_num,
        })

    return pd.DataFrame(records)


def show_tyre_analysis(year: str = None, series: str = None, race: str = None):
    """
    Display pit notes analysis.

    Parameters are passed from the sidebar so users don't have to retype them.
    Falls back to manual text inputs if called without context.
    """
    st.subheader("Pit Notes Analysis")

    if not _PDF_OK:
        st.warning("pdfplumber is not installed. Run `pip install pdfplumber` to enable pit notes parsing.")
        return

    # Use sidebar context if provided, else let user type
    if year and series and race:
        from config import DATA_DIR
        pdf_path = os.path.join(DATA_DIR, year, series, f"{race}_pitnotes.pdf")
        csv_path = os.path.join(DATA_DIR, year, series, f"{race}_pitnotes_parsed.csv")
    else:
        col1, col2, col3 = st.columns(3)
        year = col1.text_input("Year", "2026")
        series = col2.text_input("Series", "IMSA")
        race = col3.text_input("Race name prefix", "Daytona")
        from config import DATA_DIR
        pdf_path = os.path.join(DATA_DIR, year, series, f"{race}_pitnotes.pdf")
        csv_path = os.path.join(DATA_DIR, year, series, f"{race}_pitnotes_parsed.csv")

    if not os.path.exists(pdf_path):
        st.info(f"No pit notes PDF found at `{pdf_path}`.")
        return

    # Load from cached CSV if it exists, else parse
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
    else:
        df = _parse_pitnotes(pdf_path)
        if not df.empty:
            df.to_csv(csv_path, index=False)

    if df.empty:
        st.warning("No pit stop entries found in the PDF.")
        return

    # Filters
    classes = sorted(df["Class"].dropna().unique())
    selected_class = st.selectbox("Class:", ["All"] + classes, key="pitnotes_class")
    if selected_class != "All":
        df = df[df["Class"] == selected_class]

    cars = sorted(df["Car"].dropna().unique())
    selected_car = st.selectbox("Car:", ["All"] + list(cars), key="pitnotes_car")
    if selected_car != "All":
        df = df[df["Car"] == selected_car]

    drivers = sorted(set(df["Driver Out"]).union(df["Driver In"]))
    selected_driver = st.selectbox("Driver (in or out):", ["All"] + drivers, key="pitnotes_driver")
    if selected_driver != "All":
        df = df[(df["Driver Out"] == selected_driver) | (df["Driver In"] == selected_driver)]

    st.dataframe(df, use_container_width=True)

    if os.path.exists(csv_path):
        with open(csv_path, "rb") as f:
            st.download_button(
                "Download pit stops CSV",
                data=f,
                file_name=f"{race}_pitnotes_parsed.csv",
                mime="text/csv",
            )
