import html

import gspread
import streamlit as st

# Severity label -> (display text, background colour, text colour).
# Yellow gets dark text because white on yellow is unreadable.
SEVERITY = {
    "Severe": ("Severe (Red)", "#D32F2F", "#FFFFFF"),
    "Semi-severe": ("Semi-severe (Pink)", "#EC407A", "#FFFFFF"),
    "Not-severe": ("Not-severe (Yellow)", "#FDD835", "#212121"),
}
OXYGEN = ["High flow", "Normal", "None"]
N_INDICATORS = 7
HEADERS = ["Bed Number", "Severity", "Oxygen Needed"] + [
    f"Indicator {i}" for i in range(1, N_INDICATORS + 1)
]


@st.cache_resource
def get_worksheet():
    client = gspread.service_account_from_dict(dict(st.secrets["gcp_service_account"]))
    return client.open_by_url(st.secrets["sheet_url"]).sheet1


def save_row(bed, severity, oxygen, indicators):
    ws = get_worksheet()
    if not ws.row_values(1):
        ws.append_row(HEADERS)
    ws.append_row([bed, severity, oxygen] + indicators)


def input_tab():
    with st.form("input_form"):
        bed = st.number_input("Bed Number", min_value=1, step=1, value=None)
        severity = st.radio(
            "Severity",
            list(SEVERITY),
            index=None,
            format_func=lambda s: SEVERITY[s][0],
        )
        oxygen = st.radio("Oxygen Needed", OXYGEN, index=None)
        st.markdown("**Severity Indicator**")
        cols = st.columns(N_INDICATORS)
        indicators = [
            cols[i].checkbox(str(i + 1), key=f"indicator_{i + 1}")
            for i in range(N_INDICATORS)
        ]
        submitted = st.form_submit_button("Submit")

    if not submitted:
        return

    missing = [
        name
        for name, value in [("Bed Number", bed), ("Severity", severity), ("Oxygen Needed", oxygen)]
        if value is None
    ]
    if missing:
        st.error("Please fill in: " + ", ".join(missing))
        return

    try:
        save_row(int(bed), severity, oxygen, indicators)
    except Exception as e:
        st.error(f"Could not save to Google Sheet: {e}")
    else:
        st.success(f"Saved bed {int(bed)} ✓")


def display_tab():
    try:
        rows = get_worksheet().get_all_values()
    except Exception as e:
        st.error(f"Could not read Google Sheet: {e}")
        return

    if len(rows) < 2:
        st.info("No data input yet.")
        return

    bed, severity, oxygen, *flags = rows[-1]
    n_ticked = sum(flag.upper() == "TRUE" for flag in flags)
    _, bg, fg = SEVERITY.get(severity, (severity, "#9E9E9E", "#FFFFFF"))

    left, right = st.columns([1, 2], vertical_alignment="center")
    left.markdown(
        f'<div style="background:{bg}; color:{fg}; font-size:5rem; font-weight:700;'
        f' text-align:center; border-radius:0.5rem; padding:0.5rem 1rem;">'
        f"{html.escape(bed)}</div>",
        unsafe_allow_html=True,
    )
    right.markdown(
        f"### Oxygen needed: {oxygen}\n\n"
        f"### Severity indicator: {n_ticked} / {N_INDICATORS}"
    )


st.set_page_config(page_title="ER Red Alert", page_icon="🚨")
st.title("ER Red Alert")

tab_input, tab_display = st.tabs(["Input Information", "Display Information"])
with tab_input:
    input_tab()
with tab_display:
    display_tab()
