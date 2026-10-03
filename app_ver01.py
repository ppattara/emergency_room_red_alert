import html
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import gspread
import pandas as pd
import streamlit as st

N_BEDS = 25
N_INDICATORS = 7
INDICATORS = [f"SevInd{i}" for i in range(1, N_INDICATORS + 1)]
SEVERITY_OPTIONS = ["most severe", "severe", "not severe"]
OXYGEN_OPTIONS = ["high flow", "low flow", "none"]

BANGKOK = ZoneInfo("Asia/Bangkok")
TAB_NAME_FORMAT = "%Y-%m-%d %H:%M:%S"
TAB_ROWS, TAB_COLS = 30, 12
MAX_DATA_AGE = timedelta(hours=8)

# Sheet layout: patient table (header + N_BEDS rows), one blank row,
# then the nurse table (header + values).
PATIENT_HEADERS = ["Bed Number", "Bed Status", "Severity", "Oxygen Need"] + INDICATORS
NURSE_HEADERS = ["Severe Nurses", "Non-severe Nurses"]
NURSE_HEADER_ROW = N_BEDS + 2
NURSE_VALUE_ROW = N_BEDS + 3

# Dashboard colours. Text inside a coloured box is always black.
RED, PINK, YELLOW, GREY = "#EF5350", "#F8BBD0", "#FFEB3B", "#E0E0E0"
SEVERITY_COLOURS = {"most severe": RED, "severe": PINK, "not severe": YELLOW}
OXYGEN_COLOURS = {"high flow": RED, "low flow": PINK, "none": YELLOW}
SEVERE_NURSE_MIN = 5
NONSEVERE_NURSE_MIN = 20

NURSE_KEYS = {
    "severe_nurses": "number of nurses specialized in severe cases",
    "nonsevere_nurses": "number of nurses not specialized in severe cases",
}


# ---------------------------------------------------------------------------
# Plain-Python logic (no Streamlit), so it can be checked without deploying.
# Beds are a list of dicts, one per row of the data editor.
# ---------------------------------------------------------------------------


def blank_beds():
    return [
        {
            "Bed Number": bed,
            "No Patient": False,
            "Severity": None,
            "Oxygen Need": None,
            **{ind: False for ind in INDICATORS},
        }
        for bed in range(1, N_BEDS + 1)
    ]


def is_blank(value):
    return (
        value is None
        or value == ""
        or (isinstance(value, float) and math.isnan(value))
    )


def apply_edits(beds, editor_state):
    """Apply a data editor's `edited_rows` to a list of bed dicts."""
    beds = [dict(row) for row in beds]
    for row_index, changes in editor_state.get("edited_rows", {}).items():
        beds[int(row_index)].update(changes)
    return beds


def find_problems(beds, severe_nurses, nonsevere_nurses):
    """Return the reasons the data can't be saved yet (empty list if none)."""
    occupied = [row for row in beds if not row["No Patient"]]
    problems = []
    for column, label in [("Severity", "Severity"), ("Oxygen Need", "Oxygen need")]:
        missing = [str(row["Bed Number"]) for row in occupied if is_blank(row[column])]
        if missing:
            problems.append(f"{label} missing for bed(s): {', '.join(missing)}")
    for value, label in [
        (severe_nurses, NURSE_KEYS["severe_nurses"]),
        (nonsevere_nurses, NURSE_KEYS["nonsevere_nurses"]),
    ]:
        if value is None:
            problems.append(f"Enter the {label}")
        elif value != int(value) or value < 0:
            problems.append(f"The {label} must be a whole number, 0 or more")
    return problems


def build_sheet_rows(beds, severe_nurses, nonsevere_nurses):
    rows = [PATIENT_HEADERS]
    for row in beds:
        bed = int(row["Bed Number"])
        if row["No Patient"]:
            rows.append([bed, "Empty"] + [""] * (len(PATIENT_HEADERS) - 2))
        else:
            rows.append(
                [bed, "Occupied", row["Severity"], row["Oxygen Need"]]
                + [bool(row[ind]) for ind in INDICATORS]
            )
    rows.append([""])
    rows.append(NURSE_HEADERS)
    rows.append([int(severe_nurses), int(nonsevere_nurses)])
    return rows


def latest_tab(titles):
    """Return (timestamp, title) of the newest timestamp-named tab, or None."""
    stamped = []
    for title in titles:
        try:
            stamp = datetime.strptime(title, TAB_NAME_FORMAT).replace(tzinfo=BANGKOK)
        except ValueError:
            continue
        stamped.append((stamp, title))
    return max(stamped, default=None)


def parse_sheet_rows(values):
    """Turn a tab's cell values back into (beds, severe nurses, non-severe nurses)."""
    width = len(PATIENT_HEADERS)
    rows = [list(r) + [""] * (width - len(r)) for r in values]
    rows += [[""] * width] * (NURSE_VALUE_ROW + 1 - len(rows))
    if rows[0][:width] != PATIENT_HEADERS:
        raise ValueError("the tab does not start with the expected header row")

    beds = []
    for row in rows[1 : N_BEDS + 1]:
        beds.append(
            {
                "bed": row[0],
                "occupied": row[1] == "Occupied",
                "severity": row[2],
                "oxygen": row[3],
                "indicators": [cell.upper() == "TRUE" for cell in row[4:width]],
            }
        )
    severe, nonsevere = rows[NURSE_VALUE_ROW][:2]
    return beds, severe, nonsevere


def now_bangkok():
    return datetime.now(BANGKOK)


# ---------------------------------------------------------------------------
# Google Sheet access
# ---------------------------------------------------------------------------


@st.cache_resource
def get_spreadsheet():
    # Secrets use the [connections.gsheets] layout: the spreadsheet URL/key
    # plus the service-account fields in one section.
    creds = dict(st.secrets["connections"]["gsheets"])
    spreadsheet = creds.pop("spreadsheet")
    client = gspread.service_account_from_dict(creds)
    if spreadsheet.startswith("http"):
        return client.open_by_url(spreadsheet)
    return client.open_by_key(spreadsheet)


def save_to_new_tab(rows):
    spreadsheet = get_spreadsheet()
    title = now_bangkok().strftime(TAB_NAME_FORMAT)
    worksheet = spreadsheet.add_worksheet(title=title, rows=TAB_ROWS, cols=TAB_COLS)
    try:
        worksheet.update(range_name="A1", values=rows)
    except Exception:
        # Don't leave an empty tab behind: it would become the "latest" one.
        try:
            spreadsheet.del_worksheet(worksheet)
        except Exception:
            pass
        raise
    return title


# ---------------------------------------------------------------------------
# Session state
#
# The data editor's own state is lost when the user switches page, so the bed
# data is also kept in `beds_current`. The editor is drawn from `beds_base`
# under the key `beds_editor_<version>`; bumping the version starts a fresh
# editor from `beds_base`.
# ---------------------------------------------------------------------------


def editor_key():
    return f"beds_editor_{st.session_state.editor_version}"


def init_state():
    ss = st.session_state
    if "beds_current" not in ss:
        ss.beds_base = blank_beds()
        ss.beds_current = blank_beds()
        ss.editor_version = 0
        ss.save_state = None  # None, "saving" or "saved"
        ss.save_error = None
        ss.saved_tab = None
        for key in NURSE_KEYS:
            ss[key] = None
    # Re-assigning widget keys stops Streamlit from clearing them when the
    # widgets aren't drawn (i.e. while the user is on the Dashboard page).
    for key in NURSE_KEYS:
        ss[key] = ss[key]


def sync_beds():
    ss = st.session_state
    key = editor_key()
    if key in ss:
        ss.beds_current = apply_edits(ss.beds_base, ss[key])
    else:
        # The editor isn't alive (first visit, or back from another page).
        ss.beds_base = ss.beds_current


def start_save():
    ss = st.session_state
    if ss.save_state is not None:
        return
    sync_beds()
    if find_problems(ss.beds_current, ss.severe_nurses, ss.nonsevere_nurses):
        return
    # Freeze the data and lock the form before the slow write starts, so a
    # second click can't save twice.
    ss.beds_base = ss.beds_current
    ss.editor_version += 1
    ss.save_state = "saving"
    ss.save_error = None


def start_new_entry():
    ss = st.session_state
    ss.beds_base = blank_beds()
    ss.beds_current = blank_beds()
    ss.editor_version += 1
    ss.save_state = None
    ss.save_error = None
    ss.saved_tab = None
    for key in NURSE_KEYS:
        ss[key] = None


# ---------------------------------------------------------------------------
# Data Input page
# ---------------------------------------------------------------------------


def data_input_page():
    ss = st.session_state
    locked = ss.save_state is not None
    st.title("Data Input")

    edited = st.data_editor(
        pd.DataFrame(ss.beds_base),
        key=editor_key(),
        hide_index=True,
        num_rows="fixed",
        height=(N_BEDS + 1) * 35 + 3,
        disabled=True if locked else ["Bed Number"],
        column_config={
            "Bed Number": st.column_config.NumberColumn("Bed Number", width="small"),
            "No Patient": st.column_config.CheckboxColumn("No Patient", width="small"),
            "Severity": st.column_config.SelectboxColumn(
                "Severity", options=SEVERITY_OPTIONS, width="medium"
            ),
            "Oxygen Need": st.column_config.SelectboxColumn(
                "Oxygen Need", options=OXYGEN_OPTIONS, width="medium"
            ),
            **{
                ind: st.column_config.CheckboxColumn(ind, width="small")
                for ind in INDICATORS
            },
        },
    )
    ss.beds_current = edited.to_dict("records")

    st.subheader("Nurses currently in the ER")
    left, right = st.columns(2)
    for column, (key, label) in zip([left, right], NURSE_KEYS.items()):
        column.number_input(
            label.capitalize(),
            min_value=0,
            step=1,
            value=None,
            key=key,
            disabled=locked,
        )

    st.divider()
    button_col, message_col = st.columns([1, 3])
    if ss.save_state == "saved":
        button_col.button(
            "Success, start new entry?", type="primary", on_click=start_new_entry
        )
        message_col.success(f"Saved to the Google Sheet tab **{ss.saved_tab}**.")
    elif ss.save_state == "saving":
        button_col.button("Saving…", type="primary", disabled=True)
    else:
        problems = find_problems(
            ss.beds_current, ss.severe_nurses, ss.nonsevere_nurses
        )
        button_col.button(
            "Finish", type="primary", disabled=bool(problems), on_click=start_save
        )
        if ss.save_error:
            message_col.error(
                f"Could not save to the Google Sheet: {ss.save_error}\n\n"
                "Your data is still here. Please try again."
            )
        if problems:
            message_col.warning(
                "Can't save yet:\n\n" + "\n".join(f"- {p}" for p in problems)
            )

    if ss.save_state == "saving":
        rows = build_sheet_rows(ss.beds_current, ss.severe_nurses, ss.nonsevere_nurses)
        with st.spinner("Saving to the Google Sheet…"):
            # Update the state straight after the write, before any other
            # Streamlit call, so an interrupted rerun can't lose the result.
            try:
                ss.saved_tab = save_to_new_tab(rows)
                ss.save_state = "saved"
            except Exception as e:
                ss.save_error = str(e) or type(e).__name__
                ss.save_state = None
                ss.editor_version += 1  # redraw the editor unlocked
        st.rerun()


# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------

DASHBOARD_CSS = """
<style>
.er-board {overflow-x: auto;}
.er-row {display: grid; grid-template-columns: 7rem 8rem repeat(7, minmax(3.5rem, 1fr));
  gap: 0.3rem; margin-bottom: 0.3rem; min-width: 42rem;}
.er-head {font-size: 0.8rem; opacity: 0.7; text-align: center;}
.er-box {border-radius: 0.4rem; padding: 0.25rem; text-align: center; min-height: 3.6rem;
  display: flex; flex-direction: column; justify-content: center;}
.er-coloured {color: #000;}
.er-bed {font-size: 1.8rem; font-weight: 700; line-height: 1.1;}
.er-small {font-size: 0.75rem;}
.er-nurses {display: grid; grid-template-columns: repeat(2, minmax(10rem, 16rem)); gap: 1rem;}
.er-nurse-num {font-size: 3.5rem; font-weight: 700; line-height: 1.1;}
</style>
"""


def box(content, colour=None, extra_class=""):
    if colour:
        return (
            f'<div class="er-box er-coloured {extra_class}" '
            f'style="background:{colour};">{content}</div>'
        )
    return f'<div class="er-box {extra_class}">{content}</div>'


def bed_row_html(bed):
    number = f'<div class="er-bed">{html.escape(bed["bed"])}</div>'
    if not bed["occupied"]:
        return f'<div class="er-row">{box(number)}</div>'
    cells = [
        box(
            number + f'<div class="er-small">{html.escape(bed["severity"])}</div>',
            SEVERITY_COLOURS.get(bed["severity"], GREY),
        ),
        box(html.escape(bed["oxygen"]), OXYGEN_COLOURS.get(bed["oxygen"], GREY)),
    ]
    for name, ticked in zip(INDICATORS, bed["indicators"]):
        cells.append(box(name, RED if ticked else YELLOW, "er-small"))
    return f'<div class="er-row">{"".join(cells)}</div>'


def nurse_box_html(label, value, minimum):
    try:
        colour = RED if int(value) < minimum else YELLOW
    except ValueError:
        colour = GREY
    return box(
        f'<div class="er-nurse-num">{html.escape(value)}</div><div>{label}</div>',
        colour,
    )


def dashboard_page():
    st.title("Dashboard")
    no_data = "No data input yet, please go to the data input page."

    try:
        spreadsheet = get_spreadsheet()
        latest = latest_tab(ws.title for ws in spreadsheet.worksheets())
        now = now_bangkok()
        if latest is None or now - latest[0] > MAX_DATA_AGE:
            st.info(no_data)
            return
        stamp, title = latest
        beds, severe, nonsevere = parse_sheet_rows(
            spreadsheet.worksheet(title).get_all_values()
        )
    except Exception as e:
        st.error(f"Could not read the Google Sheet: {e or type(e).__name__}")
        return

    minutes = max(0, int((now - stamp).total_seconds() // 60))
    st.markdown(
        f"Data was entered at **{title}** "
        f"({minutes} minute{'' if minutes == 1 else 's'} ago)"
    )

    header = (
        '<div class="er-row">'
        '<div class="er-head">Bed / Severity</div>'
        '<div class="er-head">Oxygen</div>'
        '<div class="er-head" style="grid-column: span 7;">Severity indicators</div>'
        "</div>"
    )
    rows = "".join(bed_row_html(bed) for bed in beds)
    nurses = (
        '<div class="er-nurses">'
        + nurse_box_html("Severe Nurse", severe, SEVERE_NURSE_MIN)
        + nurse_box_html("Non-severe Nurse", nonsevere, NONSEVERE_NURSE_MIN)
        + "</div>"
    )
    st.markdown(
        DASHBOARD_CSS + f'<div class="er-board">{header}{rows}</div>',
        unsafe_allow_html=True,
    )
    st.subheader("Nurses")
    st.markdown(nurses, unsafe_allow_html=True)


# ---------------------------------------------------------------------------

st.set_page_config(page_title="ER Red Alert", page_icon="🚨", layout="wide")
init_state()
sync_beds()
page = st.navigation(
    [
        st.Page(data_input_page, title="Data Input", icon="✏️"),
        st.Page(dashboard_page, title="Dashboard", icon="📊"),
    ]
)
page.run()
