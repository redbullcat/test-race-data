import streamlit as st
import pandas as pd
import pdfplumber
import re
import os

def extract_pitnotes_info(pdf_path: str):
    with pdfplumber.open(pdf_path) as pdf:
        all_text = []
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                all_text.extend([(line, i + 1) for line in text.split("\n")])

    pit_lines = [
        (line, page_num)
        for (line, page_num) in all_text
        if re.search(r"\bpits\b", line.lower())
    ]

    pattern = re.compile(
        r"At\s(?P<local_time>\d{1,2}:\d{2}\s(?:am|pm))\s"
        r"\((?P<race_time>(?:\d+h\s)?\d+m)\)\s"
        r"(?P<driver>.+?)\s"
        r"\(#(?P<car_number>\d+)-(?P<class>\w+)[^\)]*\)\s"
        r"(?P<pos_type>CP|OP):\s\d+,\s?pits\.?\s"
        r"(?P<actions>[^\.]+)\.?\s"
        r"(?:DC:\s(?P<driver_change>[^\.]+))?\.?\s"
        r"Pit Lane:\s(?P<pit_time>\d{2}:\d{2})",
        re.IGNORECASE
    )

    data = []

    for line, page_num in pit_lines:
        match = pattern.search(line)
        if not match:
            continue

        d = match.groupdict()
        actions_text = d["actions"].lower()

        fuel_only = "fuel only" in actions_text
        fuel_tires = "fuel, tires" in actions_text or "fuel, tyre" in actions_text
        driver_change = bool(d["driver_change"]) or "driver change" in actions_text

        driver_out = d["driver"].strip()
        driver_in = d["driver_change"].strip() if d["driver_change"] else driver_out

        data.append({
            "Local Time": d["local_time"],
            "Race Time": d["race_time"],
            "Car Number": d["car_number"],
            "Class": d["class"],
            "Driver Out": driver_out,
            "Driver In": driver_in,
            "Position Type": d["pos_type"],
            "Fuel only": fuel_only,
            "Fuel, tires": fuel_tires,
            "Driver Change": driver_change,
            "Pit Lane Time": d["pit_time"],
            "Page": page_num
        })

    return pd.DataFrame(data)


def load_or_parse_pitnotes(pdf_path: str, csv_path: str):
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)

    df = extract_pitnotes_info(pdf_path)
    if not df.empty:
        df.to_csv(csv_path, index=False)
    return df


def show_tyre_analysis():
    st.header("IMSA Pit Notes Analysis")

    year = st.text_input("Enter race year", "2026")
    series = st.text_input("Enter series", "IMSA")
    race_name = st.text_input("Enter race name (filename prefix)", "Daytona")

    pdf_path = os.path.join("data", year, series, f"{race_name}_pitnotes.pdf")
    csv_path = os.path.join("data", year, series, f"{race_name}_pitnotes_parsed.csv")

    if not os.path.exists(pdf_path):
        st.error(f"PDF file not found at {pdf_path}")
        return

    if "pitnotes_df" not in st.session_state:
        st.session_state.pitnotes_df = None

    if st.button("Parse Pit Notes PDF"):
        with st.spinner("Parsing PDF (or loading cached CSV)..."):
            df = load_or_parse_pitnotes(pdf_path, csv_path)
            if df.empty:
                st.warning("No pit notes entries found.")
                return

            st.session_state.pitnotes_df = df
            st.success(f"Parsed data saved to CSV: {csv_path}")

    df = st.session_state.pitnotes_df
    if df is None or df.empty:
        st.info("Parse the pit notes PDF to begin.")
        return

    # Filters
    classes = sorted(df["Class"].dropna().unique())
    selected_class = st.selectbox("Select Class", ["All"] + classes)
    if selected_class != "All":
        df = df[df["Class"] == selected_class]

    cars = sorted(df["Car Number"].dropna().unique())
    selected_car = st.selectbox("Select Car Number", ["All"] + cars)
    if selected_car != "All":
        df = df[df["Car Number"] == selected_car]

    drivers = sorted(set(df["Driver Out"]).union(df["Driver In"]))
    selected_driver = st.selectbox("Select Driver (Out or In)", ["All"] + drivers)
    if selected_driver != "All":
        df = df[(df["Driver Out"] == selected_driver) | (df["Driver In"] == selected_driver)]

    st.dataframe(df, use_container_width=True)

    # Download cached CSV
    if os.path.exists(csv_path):
        with open(csv_path, "rb") as f:
            st.download_button(
                label="Download pit stop CSV",
                data=f,
                file_name=f"{race_name}_pitnotes_parsed.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    show_tyre_analysis()
