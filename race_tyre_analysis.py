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
                all_text.extend([(line, i+1) for line in text.split("\n")])

    # Filter lines with "pits" or "pit"
    pit_lines = [(line, page_num) for (line, page_num) in all_text if re.search(r"\bpits\b", line.lower())]

    # Regex with optional DC and flexible position
    pattern = re.compile(
        r"At\s(?P<local_time>\d{1,2}:\d{2}\s(?:am|pm))\s"
        r"\((?P<race_time>(?:\d+h\s)?\d+m)\)\s"
        r"(?P<driver>.+?)\s"
        r"\(#(?P<car_number>\d+)-(?P<class>\w+)[^\)]*\)\s"
        r"(?P<pos_type>CP|OP):\s\d+,\s?pits\.?\s"
        r"(?P<actions>fuel(?: only|, tires?)?(?:, driver change)?|fuel, tires|fuel, tires, driver change|fuel only)\.?"
        r"(?:\sDC:\s(?P<driver_change>[^\.]+))?\.?\s"
        r"Pit Lane:\s(?P<pit_time>\d{2}:\d{2})",
        re.IGNORECASE
    )

    data = []
    for line, page_num in pit_lines:
        match = pattern.search(line)
        if match:
            d = match.groupdict()
            actions_text = d['actions'].lower()
            fuel_only = 'fuel only' in actions_text
            fuel_tires = 'fuel, tires' in actions_text or 'fuel, tyre' in actions_text
            driver_change = bool(d['driver_change']) or 'driver change' in actions_text

            data.append({
                'Local Time': d['local_time'],
                'Race Time': d['race_time'],
                'Car Number': d['car_number'],
                'Class': d['class'],
                'Driver': d['driver'].strip(),
                'Position Type': d['pos_type'],
                'Fuel only': fuel_only,
                'Fuel, tires': fuel_tires,
                'Driver Change': driver_change,
                'Pit Lane Time': d['pit_time'],
                'Page': page_num
            })

    df = pd.DataFrame(data)
    return df

def show_tyre_analysis():
    st.header("IMSA Pit Notes Analysis")

    year = st.text_input("Enter race year", "2026")
    series = st.text_input("Enter series", "IMSA")
    race_name = st.text_input("Enter race name (filename prefix)", "Daytona")

    pdf_path = os.path.join("data", year, series, f"{race_name}_pitnotes.pdf")

    if not os.path.exists(pdf_path):
        st.error(f"PDF file not found at {pdf_path}")
        return

    st.write(f"Reading pit notes PDF from: {pdf_path}")

    if st.button("Parse Pit Notes PDF"):
        with st.spinner("Parsing PDF..."):
            df = extract_pitnotes_info(pdf_path)
            if df.empty:
                st.warning("No pit notes entries found.")
            else:
                st.dataframe(df)

if __name__ == "__main__":
    show_tyre_analysis()
