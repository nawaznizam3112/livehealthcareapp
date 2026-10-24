
# CashlessReady MVP

A Streamlit and SQLite prototype for tracking hospital cashless
pre-authorization readiness.

## Features

- Case register, search and status filters
- Create and edit cases
- Illustrative document checklist
- Insurer/TPA query and deadline tracking
- SQLite database
- CSV export
- Optional Gemini AI administrative draft review
- Case event history
- Synthetic demo cases

## Deploy on Streamlit Community Cloud

1. Upload app.py and requirements.txt to a GitHub repository.
2. Open https://share.streamlit.io/
3. Sign in with GitHub.
4. Create a new app.
5. Select your repository and branch.
6. Set the main file path to app.py.
7. Click Deploy.

## Optional Gemini AI

In Streamlit app settings, open Secrets and add:

GEMINI_API_KEY = "YOUR_API_KEY"

Never commit your API key to GitHub.

## Important limitations

This is an MVP, not a hospital-grade application.

Use synthetic/demo data only. Do not enter real patient data.

The checklist is illustrative and must be verified against
the relevant hospital and insurer/TPA requirements.

AI output may be inaccurate and requires human review.

The app has no authentication, role-based access, insurer/TPA
integration, automated submission, or production-grade audit controls.

SQLite on Streamlit Community Cloud is not reliable persistent
storage for a live multi-user service.

Before a real hospital pilot, add authentication, permissions,
a managed persistent database, backups, and appropriate privacy
and security controls.
