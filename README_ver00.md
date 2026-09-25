# ER Red Alert — Demo (ver00)

A minimal Streamlit web app for the emergency-room red-alert project. The demo
shows one round trip: enter one patient's status in a form, save it to a
private Google Sheet, then read it back from the sheet and display it.

This is a demo only. Ideas for the full version are in
`future_considerations.md`.

## Files

| File | Purpose |
|---|---|
| `code_requirements_ver00.txt` | Spec for this demo |
| `code_requirements_ver01.txt` | Draft spec for the full program |
| `app_ver00.py` | The Streamlit app |
| `requirements.txt` | Python packages for Streamlit Community Cloud |
| `future_considerations.md` | Review notes set aside for after the demo |

## What the app does

The page has two tabs.

### Input Information

A form with:

- **Bed Number**: a whole number, 1 or higher.
- **Severity**: pick one of Severe (Red), Semi-severe (Pink), Not-severe (Yellow).
- **Oxygen Needed**: pick one of High flow, Normal, None.
- **Severity Indicator**: 7 checkboxes labelled 1 to 7. Any number can be ticked.
- **Submit** button.

If Bed Number, Severity or Oxygen Needed is missing when you press Submit, the
app says which fields to fill in. Otherwise it saves the entry to the Google
Sheet and shows "Saved bed N ✓", or an error if the write fails.

### Display Information

Reads the Google Sheet and shows the **last** data row:

- The bed number in large text, on a background of the severity colour.
- The oxygen need, next to the bed number.
- The severity indicator, as the number of ticked boxes out of 7 (e.g. `3 / 7`).

If the sheet has no data rows yet, it shows "No data input yet."

## Google Sheet format

The first sheet (tab) of the spreadsheet is used. If row 1 is empty, the app
writes this header row before the first entry:

| Bed Number | Severity | Oxygen Needed | Indicator 1 | … | Indicator 7 |
|---|---|---|---|---|---|
| 5 | Severe | High flow | TRUE | … | FALSE |

- **Severity** stores `Severe`, `Semi-severe` or `Not-severe`.
- **Oxygen Needed** stores `High flow`, `Normal` or `None`.
- **Indicator 1–7** store `TRUE` / `FALSE`.

Each Submit appends a new row. The Display tab always shows the last one.

## Setup

### 1. Share the sheet

Share the Google Sheet (Editor access) with the service account's
`client_email`.

### 2. Add secrets

Locally, create `.streamlit/secrets.toml`. On Streamlit Community Cloud, paste
the same content into the app's **Settings → Secrets**.

```toml
sheet_url = "https://docs.google.com/spreadsheets/d/..."

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "...@....iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

The fields under `[gcp_service_account]` are the ones in the service account's
JSON key file. Never commit `secrets.toml` to the repo.

### 3. Run locally

```bash
pip install -r requirements.txt
streamlit run app_ver00.py
```

### 4. Deploy

On Streamlit Community Cloud, create a new app from the repo and set the main
file to `app_ver00.py`. `requirements.txt` is installed automatically.

## Changes from the first draft of the spec

Agreed during review, and reflected in `code_requirements_ver00.txt`:

- Severity and Oxygen Needed are radio buttons (pick one), not checkboxes, so
  contradictory selections are impossible.
- Severity and Oxygen Needed are stored as one column each, not 3 TRUE/FALSE
  columns.
- The Display tab reads from the Google Sheet, not from a cache, so the demo
  proves the data really reached the sheet.
- The Display tab shows "No data input yet." when the sheet is empty.

Decided while building the app:

- The app writes the header row itself when the sheet is empty.
- The bed number is dark text on yellow, and white text on red and pink, so it
  stays readable.
- If there is more than one data row, the Display tab shows the last one.

## Status

- `app_ver00.py` passes a Python syntax check.
- The app has **not** been run yet: Streamlit is not installed on the
  development machine, and it has not been connected to the Google Sheet.
