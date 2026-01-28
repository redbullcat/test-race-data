import streamlit as st
import pandas as pd
import pdfplumber
import requests
import tempfile
import re


# ----------------------------
# PDF download
# ----------------------------

def download_pdf(url: str) -> str:
    response = requests.get(url)
    response.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(response.content)
    tmp.close()

    return tmp.name


# ----------------------------
# Extract text with page refs
# ----------------------------

def extract_pdf_lines(pdf_path: str) -> list[dict]:
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                rows.append(
                    {
                        "PAGE": page_num,
                        "RAW_LINE": line.strip(),
                    }
                )

    return rows


# ----------------------------
# Parse pit stop lines
# ----------------------------

def parse_pit_lines(lines: list[dict]) -> pd.DataFrame:
    pit_lines = [
        row for row in lines
        if "pits" in row["RAW_LINE"].lower()
    ]

    records = []

    for row in pit_lines:
        text = row["RAW_LINE"]

        # Time of day
        clock_time = None
        m = re.search(r"At\s+([0-9:]+\s*(?:am|pm))", text, re.IGNORECASE)
        if m:
            clock_time = m.group(1)

        # Time into race
        race_time = None
        m = re.search(r"\((\d+h\s*\d+m)\)", text)
        if m:
            race_time = m.group(1)

        # Car + class
        car = None
        car_class = None
        m = re.search(r"#(\d+)-([A-Z0-9]+)", text)
        if m:
            car = m.group(1)
            car_class = m.group(2)

        # Pit lane time
        pit_lane_time = None
        m = re.search(r"Pit Lane:\s*([0-9:.]+)", text)
        if m:
            pit_lane_time = m.group(1)

        records.append(
            {
                "PAGE": row["PAGE"],
                "CLOCK_TIME": clock_time,
                "RACE_TIME": race_time,
                "CAR": car,
                "CLASS": car_class,
                "FUEL_ONLY": "Fuel only" in text,
                "FUEL_TYRES": "Fuel, tires" in text,
                "DRIVER_CHANGE": "DC:" in text,
                "PIT_LANE_TIME": pit_lane_time,
                "RAW_LINE": text,
            }
        )

    return pd.DataFrame(records)


# ----------------------------
# Streamlit entry point
# ----------------------------

def show_tyre_analysis(df=None):
    """
    This intentionally ignores the race CSV.
    It is a standalone PitNotes PDF parser.
    """

    st.subheader("Pit lane activity (PitNotes PDF)")

    pdf_url = st.text_input(
        "PitNotes PDF URL",
        value="https://www.pitnotes.org/files/IMSA/2026/1/Report01.pdf",
    )

    if st.button("Parse PitNotes PDF"):
        with st.spinner("Downloading PDF…"):
            pdf_path = download_pdf(pdf_url)

        with st.spinner("Extracting text…"):
            lines = extract_pdf_lines(pdf_path)

        with st.spinner("Parsing pit stops…"):
            pit_df = parse_pit_lines(lines)

        st.success(f"Found {len(pit_df)} pit stop entries")

        st.dataframe(
            pit_df,
            use_container_width=True,
            height=600,
        )

        st.download_button(
            label="Download CSV",
            data=pit_df.to_csv(index=False),
            file_name="pitnotes_pitstops.csv",
            mime="text/csv",
        )
