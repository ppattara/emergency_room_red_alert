# ER Red Alert (ver01)

A Streamlit web app for the emergency-room red alert. A nurse enters the
status of all 25 beds and the number of nurses in the ER. The data is saved to
a new tab in a private Google Sheet, and a Dashboard page shows it.

Spec: `code_requirements_ver01.txt`. Points set aside for later versions are
in `future_considerations_ver01.md`.

## Files

| File | Purpose |
|---|---|
| `app_ver01.py` | The Streamlit app (this version) |
| `requirements.txt` | Python packages for Streamlit Community Cloud |
| `code_requirements_ver01.txt` | Spec for this version |
| `future_considerations_ver01.md` | Review notes for later versions |
| `app_ver00.py`, `README_ver00.md` | The earlier one-row demo |

## Pages

Use the sidebar to switch between the two pages.

### Data Input

- A table of 25 beds with these columns: **Bed Number** (locked), **No Patient**,
  **Severity** (`most severe` / `severe` / `not severe`), **Oxygen Need**
  (`high flow` / `low flow` / `none`), and **SevInd1** to **SevInd7** checkboxes.
- Two number fields for the nurses in the ER. They only accept whole numbers,
  0 or more.
- Half-entered data is kept when you switch to the Dashboard and back.
- **Finish** stays disabled until every occupied bed (No Patient not ticked)
  has a severity and an oxygen need, and both nurse numbers are filled in. The
  message next to the button lists what is missing.
- After you click Finish, the form locks and the button shows "Saving…".
  - If the save works, the button changes to **Success, start new entry?**.
    Clicking it clears the form for a new entry.
  - If the save fails, an error appears, the form unlocks with your data still
    in it, and you can try again.

### Dashboard

- Reads the newest tab whose name is a timestamp. Other tabs, like `Sheet1`,
  are ignored.
- If there is no such tab, or the newest one is more than 8 hours old, it shows
  "No data input yet, please go to the data input page."
- Otherwise it shows "Data was entered at … (x minutes ago)", then one row per
  bed and the two nurse numbers:

| Item | Red | Pink | Yellow |
|---|---|---|---|
| Bed box (bed number + severity) | most severe | severe | not severe |
| Oxygen box | high flow | low flow | none |
| Each SevInd box | ticked | | not ticked |
| Severe Nurse | fewer than 5 | | 5 or more |
| Non-severe Nurse | fewer than 20 | | 20 or more |

  Empty beds show only the bed number, with no colour. Text in coloured boxes
  is always black, so it stays readable in dark mode.

## Google Sheet format

Each Finish creates a new tab, 30 rows × 12 columns, named with the Bangkok
time of the save, e.g. `2026-10-03 14:05:09`.

| Rows | Content |
|---|---|
| 1 | `Bed Number`, `Bed Status`, `Severity`, `Oxygen Need`, `SevInd1` … `SevInd7` |
| 2–26 | One row per bed. `Bed Status` is `Occupied` or `Empty`. Empty beds have the other cells blank. Indicators are `TRUE`/`FALSE`. |
| 27 | Blank |
| 28 | `Severe Nurses`, `Non-severe Nurses` |
| 29 | The two numbers |

## Setup and deploy

1. Share the Google Sheet (Editor access) with the service account's
   `client_email`.
2. Secrets are unchanged from ver00: paste the contents of `secrets.toml` into
   the app's **Settings → Secrets** on Streamlit Community Cloud.
3. The app's main file must be `app_ver01.py`. Community Cloud can't change the
   main file of an existing app, so delete the ver00 app and deploy a new one
   from the repo with `app_ver01.py` as the main file.

## Decisions made while building

- **No Patient** starts unticked, so every bed must be either marked empty or
  given a severity and oxygen need before saving.
- After a successful save, the table and nurse fields stay locked (read-only)
  until you click "Success, start new entry?", so it's clear nothing new is
  waiting to be saved.
- If the new tab is created but writing the data to it fails, the app deletes
  that tab. Otherwise an empty tab would become the "latest" one on the
  Dashboard.
- The Dashboard shows a small heading row (Bed / Severity, Oxygen, Severity
  indicators) above the bed rows.
- If two saves happen in the same second, the second fails because the tab
  name already exists. The user just clicks Finish again.

## Status

- The sheet-format, validation and timestamp logic was checked locally with
  plain Python.
- The Streamlit pages have **not** been run yet: Streamlit is not installed on
  the development machine. They need to be checked on Community Cloud.
