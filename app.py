
import os
import json
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

APP_TITLE = "CashlessReady | Pre-Authorization Tracker"
DB_PATH = Path(os.getenv("CASHLESSREADY_DB", "cashlessready.db"))

DOCUMENTS = [
    "Patient ID / identity proof",
    "Health insurance card / policy details",
    "Treating doctor's notes",
    "Proposed treatment / procedure plan",
    "Relevant investigation reports",
    "Estimate / cost breakup",
    "Admission advice / planned admission details",
    "Previous treatment records (if applicable)",
]

STATUSES = [
    "Draft",
    "Documents pending",
    "Ready for staff review",
    "Submitted by hospital",
    "Query received",
    "Resubmission pending",
    "Approved by insurer/TPA",
    "Rejected by insurer/TPA",
    "Discharged / closed",
]

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="📋",
    layout="wide",
)


# ---------------- DATABASE ----------------

def connect_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                hospital_name TEXT NOT NULL,
                internal_reference TEXT,
                patient_label TEXT NOT NULL,
                insurer_tpa TEXT,
                department TEXT,
                planned_procedure TEXT,
                planned_admission_date TEXT,
                estimated_amount REAL DEFAULT 0,
                status TEXT NOT NULL,
                query_deadline TEXT,
                query_notes TEXT,
                staff_notes TEXT,
                document_json TEXT NOT NULL DEFAULT '{}',
                ai_summary TEXT,
                ai_updated_at TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS case_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                event_time TEXT NOT NULL,
                event_type TEXT NOT NULL,
                details TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES cases(id)
            )
        """)

        conn.commit()


def log_event(conn, case_id, event_type, details):
    conn.execute(
        """
        INSERT INTO case_events
        (case_id, event_time, event_type, details)
        VALUES (?, ?, ?, ?)
        """,
        (
            case_id,
            datetime.now().isoformat(timespec="seconds"),
            event_type,
            details,
        ),
    )


def load_cases():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM cases ORDER BY updated_at DESC"
        ).fetchall()

    records = []

    for row in rows:
        item = dict(row)

        try:
            item["documents"] = json.loads(
                item.pop("document_json") or "{}"
            )
        except json.JSONDecodeError:
            item["documents"] = {}
            item.pop("document_json", None)

        records.append(item)

    return records


def get_case(case_id):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT * FROM cases WHERE id = ?",
            (case_id,),
        ).fetchone()

    if not row:
        return None

    item = dict(row)

    try:
        item["documents"] = json.loads(
            item.pop("document_json") or "{}"
        )
    except json.JSONDecodeError:
        item["documents"] = {}
        item.pop("document_json", None)

    return item


def save_case(data, case_id=None):
    now = datetime.now().isoformat(timespec="seconds")
    docs_json = json.dumps(
        data["documents"],
        ensure_ascii=False,
    )

    with connect_db() as conn:

        if case_id:
            old = conn.execute(
                "SELECT id FROM cases WHERE id = ?",
                (case_id,),
            ).fetchone()

            if not old:
                raise ValueError(
                    "The selected case no longer exists."
                )

            conn.execute("""
                UPDATE cases SET
                    updated_at=?,
                    hospital_name=?,
                    internal_reference=?,
                    patient_label=?,
                    insurer_tpa=?,
                    department=?,
                    planned_procedure=?,
                    planned_admission_date=?,
                    estimated_amount=?,
                    status=?,
                    query_deadline=?,
                    query_notes=?,
                    staff_notes=?,
                    document_json=?
                WHERE id=?
            """, (
                now,
                data["hospital_name"],
                data["internal_reference"],
                data["patient_label"],
                data["insurer_tpa"],
                data["department"],
                data["planned_procedure"],
                data["planned_admission_date"],
                data["estimated_amount"],
                data["status"],
                data["query_deadline"],
                data["query_notes"],
                data["staff_notes"],
                docs_json,
                case_id,
            ))

            log_event(
                conn,
                case_id,
                "Case updated",
                f"Status: {data['status']}",
            )

            result_id = case_id

        else:
            result_id = "CR-" + uuid.uuid4().hex[:8].upper()

            conn.execute("""
                INSERT INTO cases (
                    id, created_at, updated_at,
                    hospital_name, internal_reference,
                    patient_label, insurer_tpa,
                    department, planned_procedure,
                    planned_admission_date, estimated_amount,
                    status, query_deadline, query_notes,
                    staff_notes, document_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result_id,
                now,
                now,
                data["hospital_name"],
                data["internal_reference"],
                data["patient_label"],
                data["insurer_tpa"],
                data["department"],
                data["planned_procedure"],
                data["planned_admission_date"],
                data["estimated_amount"],
                data["status"],
                data["query_deadline"],
                data["query_notes"],
                data["staff_notes"],
                docs_json,
            ))

            log_event(
                conn,
                result_id,
                "Case created",
                f"Initial status: {data['status']}",
            )

        conn.commit()

    return result_id


def get_events(case_id):
    with connect_db() as conn:
        return conn.execute(
            """
            SELECT event_time, event_type, details
            FROM case_events
            WHERE case_id=?
            ORDER BY id DESC
            """,
            (case_id,),
        ).fetchall()


# ---------------- OPTIONAL GEMINI AI ----------------

def get_api_key():
    key = os.getenv("GEMINI_API_KEY", "").strip()

    if key:
        return key

    try:
        return st.secrets.get("GEMINI_API_KEY", "").strip()
    except Exception:
        return ""


def make_ai_summary(case_data):
    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "Gemini API key is not configured. Add GEMINI_API_KEY "
            "to Streamlit Secrets or your environment variables. "
            "The rest of the app works without AI."
        )

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "Install dependencies using: pip install -r requirements.txt"
        ) from exc

    safe_case = {
        "hospital": case_data["hospital_name"],
        "internal_reference": case_data["internal_reference"],
        "insurer_or_tpa": case_data["insurer_tpa"],
        "department": case_data["department"],
        "planned_procedure": case_data["planned_procedure"],
        "planned_admission_date": case_data["planned_admission_date"],
        "estimated_amount": case_data["estimated_amount"],
        "status": case_data["status"],
        "document_checklist": case_data["documents"],
        "query_notes": case_data["query_notes"],
        "staff_notes": case_data["staff_notes"],
    }

    prompt = f"""
You assist hospital administrative staff preparing a cashless
pre-authorization file.

You are NOT an insurer, TPA, doctor, legal adviser, or approval predictor.

Do not claim that any document is legally or universally required.
Requirements vary and must be checked against the hospital's current
insurer/TPA checklist.

Do not invent clinical facts, policy terms, coverage, medical necessity,
or approval likelihood. Use only the supplied information.
Identify unknowns clearly.

Return concise Markdown with these headings:
1. Case snapshot
2. Checklist items marked missing
3. Questions for hospital staff to verify
4. Suggested administrative next steps
5. Draft neutral summary for staff review

Never include a patient name, phone number, address, government ID,
or policy number.

Data:
{json.dumps(safe_case, ensure_ascii=False, indent=2)}
"""

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    output = (getattr(response, "text", None) or "").strip()

    if not output:
        raise RuntimeError(
            "Gemini returned an empty response. Please try again."
        )

    return output


# ---------------- FORM DEFAULTS ----------------

def case_to_form_data(case=None):
    case = case or {}
    docs = case.get("documents", {})

    return {
        "hospital_name": case.get("hospital_name", ""),
        "internal_reference": case.get("internal_reference", ""),
        "patient_label": case.get("patient_label", ""),
        "insurer_tpa": case.get("insurer_tpa", ""),
        "department": case.get("department", ""),
        "planned_procedure": case.get("planned_procedure", ""),
        "planned_admission_date": (
            case.get("planned_admission_date") or ""
        ),
        "estimated_amount": float(
            case.get("estimated_amount") or 0
        ),
        "status": case.get("status", "Draft"),
        "query_deadline": case.get("query_deadline") or "",
        "query_notes": case.get("query_notes", ""),
        "staff_notes": case.get("staff_notes", ""),
        "documents": {
            name: bool(docs.get(name, False))
            for name in DOCUMENTS
        },
    }


init_db()


# ---------------- APP HEADER ----------------

st.title("📋 CashlessReady")

st.caption(
    "Hospital cashless pre-authorization workflow tracker — pilot MVP"
)

st.warning(
    "Prototype safety notice: use synthetic/demo data only. "
    "Do not enter patient names, phone numbers, addresses, Aadhaar "
    "numbers, policy numbers, medical record numbers, or identifiable "
    "clinical notes. This app is not security-audited or approved "
    "for production use."
)


# ---------------- SIDEBAR ----------------

with st.sidebar:
    st.header("Workspace")
    st.write("Local SQLite database")
    st.caption(f"Database file: `{DB_PATH}`")

    st.divider()

    st.subheader("How to use")

    st.markdown(
        "1. Create a case using a non-identifying label.\n"
        "2. Tick documents confirmed by staff.\n"
        "3. Update the case status as work progresses.\n"
        "4. Export the register for a pilot review."
    )

    st.caption(
        "Checklist is illustrative. Verify it with each hospital "
        "and insurer/TPA."
    )


# ---------------- DASHBOARD DATA ----------------

cases = load_cases()
df_rows = []

for c in cases:
    missing = [
        d for d in DOCUMENTS
        if not c["documents"].get(d, False)
    ]

    df_rows.append({
        "Case ID": c["id"],
        "Updated": c["updated_at"].replace("T", " "),
        "Hospital": c["hospital_name"],
        "Internal ref": c["internal_reference"],
        "Case label": c["patient_label"],
        "Insurer / TPA": c["insurer_tpa"],
        "Procedure": c["planned_procedure"],
        "Admission date": c["planned_admission_date"],
        "Estimate (₹)": c["estimated_amount"],
        "Status": c["status"],
        "Missing checklist items": len(missing),
        "Query deadline": c["query_deadline"],
    })

df = pd.DataFrame(df_rows)

total_cases = len(cases)

open_cases = sum(
    c["status"] != "Discharged / closed"
    for c in cases
)

query_cases = sum(
    c["status"] in ("Query received", "Resubmission pending")
    for c in cases
)

ready_cases = sum(
    c["status"] == "Ready for staff review"
    for c in cases
)

m1, m2, m3, m4 = st.columns(4)

m1.metric("Total cases", total_cases)
m2.metric("Open cases", open_cases)
m3.metric("Query / resubmission", query_cases)
m4.metric("Ready for review", ready_cases)


# ---------------- TABS ----------------

tab_dashboard, tab_case, tab_ai, tab_history = st.tabs([
    "Case register",
    "Create / edit case",
    "AI admin assistant",
    "Case history",
])


# ---------------- CASE REGISTER ----------------

with tab_dashboard:
    st.subheader("Case register")

    if df.empty:
        st.info(
            "No cases yet. Create a case in the Create / edit case "
            "tab, or load demo cases below."
        )

    else:
        f1, f2 = st.columns([1, 2])

        with f1:
            status_filter = st.multiselect(
                "Filter by status",
                options=STATUSES,
                default=[],
            )

        with f2:
            search_text = st.text_input(
                "Search cases",
                placeholder="Case ID, hospital, label, insurer, procedure",
            )

        view = df.copy()

        if status_filter:
            view = view[view["Status"].isin(status_filter)]

        if search_text.strip():
            q = search_text.strip().lower()

            mask = view.astype(str).apply(
                lambda col: col.str.lower().str.contains(
                    q,
                    na=False,
                    regex=False,
                )
            ).any(axis=1)

            view = view[mask]

        st.dataframe(
            view,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download visible register as CSV",
            data=view.to_csv(index=False).encode("utf-8-sig"),
            file_name="cashlessready_case_register.csv",
            mime="text/csv",
        )

    if st.button(
        "Load synthetic demo cases",
        help="Adds sample records only if the database is empty.",
    ):
        if load_cases():
            st.info(
                "Your database already has cases; demo cases were not added."
            )

        else:
            examples = [
                {
                    "hospital_name": "Demo Hospital A",
                    "internal_reference": "DEMO-001",
                    "patient_label": "Synthetic Case A",
                    "insurer_tpa": "Example TPA",
                    "department": "Orthopaedics",
                    "planned_procedure": "Illustrative knee procedure",
                    "planned_admission_date": str(date.today()),
                    "estimated_amount": 85000,
                    "status": "Documents pending",
                    "query_deadline": "",
                    "query_notes": "",
                    "staff_notes": "Synthetic example only.",
                    "documents": {
                        d: d in (
                            "Patient ID / identity proof",
                            "Treating doctor's notes",
                        )
                        for d in DOCUMENTS
                    },
                },
                {
                    "hospital_name": "Demo Hospital B",
                    "internal_reference": "DEMO-002",
                    "patient_label": "Synthetic Case B",
                    "insurer_tpa": "Example Insurer",
                    "department": "General Surgery",
                    "planned_procedure": "Illustrative elective procedure",
                    "planned_admission_date": str(date.today()),
                    "estimated_amount": 42000,
                    "status": "Query received",
                    "query_deadline": str(date.today()),
                    "query_notes": (
                        "Demo query: provide additional supporting report."
                    ),
                    "staff_notes": "Synthetic example only.",
                    "documents": {
                        d: True for d in DOCUMENTS
                    },
                },
            ]

            for example in examples:
                save_case(example)

            st.success("Added two synthetic demo cases.")
            st.rerun()


# ---------------- CREATE / EDIT CASE ----------------

with tab_case:
    st.subheader("Create or edit a case")

    existing_cases = load_cases()

    choices = {"➕ New case": None}

    for c in existing_cases:
        choices[
            f'{c["id"]} — {c["patient_label"]} — {c["status"]}'
        ] = c["id"]

    selected_label = st.selectbox(
        "Choose a case to edit, or create a new one",
        list(choices.keys()),
    )

    selected_id = choices[selected_label]

    current = get_case(selected_id) if selected_id else None
    defaults = case_to_form_data(current)

    with st.form("case_form", clear_on_submit=False):
        st.markdown("**Case details**")

        col1, col2 = st.columns(2)

        with col1:
            hospital_name = st.text_input(
                "Hospital / facility name *",
                value=defaults["hospital_name"],
            )

            internal_reference = st.text_input(
                "Hospital internal reference (no patient ID)",
                value=defaults["internal_reference"],
            )

            patient_label = st.text_input(
                "Non-identifying case label *",
                value=defaults["patient_label"],
                help="Example: Synthetic Case A. Do not enter a patient's name.",
            )

            insurer_tpa = st.text_input(
                "Insurer / TPA",
                value=defaults["insurer_tpa"],
            )

            department = st.text_input(
                "Department",
                value=defaults["department"],
            )

        with col2:
            planned_procedure = st.text_input(
                "Planned procedure (brief, non-identifying)",
                value=defaults["planned_procedure"],
            )

            planned_admission_date = st.text_input(
                "Planned admission date (YYYY-MM-DD)",
                value=defaults["planned_admission_date"],
            )

            estimated_amount = st.number_input(
                "Estimated amount (₹)",
                min_value=0.0,
                step=1000.0,
                value=max(0.0, defaults["estimated_amount"]),
            )

            status = st.selectbox(
                "Workflow status",
                STATUSES,
                index=(
                    STATUSES.index(defaults["status"])
                    if defaults["status"] in STATUSES
                    else 0
                ),
            )

            query_deadline = st.text_input(
                "Query response deadline (YYYY-MM-DD)",
                value=defaults["query_deadline"],
            )

        query_notes = st.text_area(
            "Insurer / TPA query notes (remove identifiers)",
            value=defaults["query_notes"],
            height=90,
        )

        staff_notes = st.text_area(
            "Administrative notes (remove identifiers)",
            value=defaults["staff_notes"],
            height=90,
        )

        st.markdown("**Document checklist**")

        st.caption(
            "Tick only when staff has confirmed that the item is present. "
            "This is not a universal payer requirement list."
        )

        doc_values = {}
        doc_cols = st.columns(2)

        for i, doc in enumerate(DOCUMENTS):
            with doc_cols[i % 2]:
                doc_values[doc] = st.checkbox(
                    doc,
                    value=defaults["documents"].get(doc, False),
                    key=f"doc_{selected_id or 'new'}_{i}",
                )

        submitted = st.form_submit_button(
            "Save case",
            type="primary",
        )

        if submitted:
            if not hospital_name.strip() or not patient_label.strip():
                st.error(
                    "Hospital name and a non-identifying case label are required."
                )

            else:
                data = {
                    "hospital_name": hospital_name.strip(),
                    "internal_reference": internal_reference.strip(),
                    "patient_label": patient_label.strip(),
                    "insurer_tpa": insurer_tpa.strip(),
                    "department": department.strip(),
                    "planned_procedure": planned_procedure.strip(),
                    "planned_admission_date": planned_admission_date.strip(),
                    "estimated_amount": float(estimated_amount),
                    "status": status,
                    "query_deadline": query_deadline.strip(),
                    "query_notes": query_notes.strip(),
                    "staff_notes": staff_notes.strip(),
                    "documents": doc_values,
                }

                saved_id = save_case(data, selected_id)

                st.success(f"Saved case {saved_id}.")
                st.rerun()


# ---------------- AI ADMIN ASSISTANT ----------------

with tab_ai:
    st.subheader("AI administrative review")

    st.write(
        "Creates a draft checklist review from the fields you entered. "
        "It does not decide coverage, medical necessity, approval, or "
        "insurer compliance. A staff member must verify all output."
    )

    ai_cases = load_cases()

    if not ai_cases:
        st.info("Create a case first to use the AI assistant.")

    else:
        ai_options = {
            f'{c["id"]} — {c["patient_label"]}': c["id"]
            for c in ai_cases
        }

        ai_label = st.selectbox(
            "Select case for review",
            list(ai_options.keys()),
            key="ai_case_select",
        )

        ai_case_id = ai_options[ai_label]
        ai_case = get_case(ai_case_id)

        missing_docs = [
            d for d in DOCUMENTS
            if not ai_case["documents"].get(d, False)
        ]

        st.markdown("**Local checklist snapshot**")

        if missing_docs:
            st.warning(
                "Unchecked checklist items: "
                + "; ".join(missing_docs)
            )
        else:
            st.success(
                "All items in this illustrative checklist are marked present. "
                "Verify against the current hospital/TPA checklist."
            )

        if st.button(
            "Generate AI administrative review",
            type="primary",
        ):
            try:
                with st.spinner("Generating a draft review…"):
                    review = make_ai_summary(ai_case)

                now = datetime.now().isoformat(timespec="seconds")

                with connect_db() as conn:
                    conn.execute(
                        """
                        UPDATE cases
                        SET ai_summary=?, ai_updated_at=?, updated_at=?
                        WHERE id=?
                        """,
                        (
                            review,
                            now,
                            now,
                            ai_case_id,
                        ),
                    )

                    log_event(
                        conn,
                        ai_case_id,
                        "AI review generated",
                        "Generated draft administrative review.",
                    )

                    conn.commit()

                st.success("Draft review saved to this case.")
                st.rerun()

            except Exception as exc:
                st.error(str(exc))

        latest = get_case(ai_case_id)

        if latest and latest.get("ai_summary"):
            st.markdown("### Saved AI review")

            st.caption(
                f"Generated: {latest.get('ai_updated_at') or 'Unknown'}"
            )

            st.markdown(latest["ai_summary"])

            st.download_button(
                "Download AI review as Markdown",
                data=latest["ai_summary"].encode("utf-8"),
                file_name=f"{ai_case_id}_admin_review.md",
                mime="text/markdown",
            )


# ---------------- CASE HISTORY ----------------

with tab_history:
    st.subheader("Case event history")

    history_cases = load_cases()

    if not history_cases:
        st.info("No cases available yet.")

    else:
        history_options = {
            f'{c["id"]} — {c["patient_label"]}': c["id"]
            for c in history_cases
        }

        history_label = st.selectbox(
            "Select case",
            list(history_options.keys()),
            key="history_case_select",
        )

        history_id = history_options[history_label]
        events = get_events(history_id)

        if events:
            st.dataframe(
                pd.DataFrame([dict(e) for e in events]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No history entries yet.")


# ---------------- FOOTER ----------------

st.divider()

st.caption(
    "CashlessReady MVP • Local database only • No insurer/TPA integration • "
    "No authentication or role permissions • Not for production patient data "
    "until security, privacy, retention, backup, and legal requirements are assessed."
)


   
