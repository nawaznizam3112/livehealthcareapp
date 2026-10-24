
import os
import json
from datetime import date, datetime

import pandas as pd
import streamlit as st
from supabase import create_client, Client

st.set_page_config(
    page_title="CashlessReady",
    page_icon="📋",
    layout="wide",
)

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


def get_secret(name):
    try:
        return st.secrets.get(name, "")
    except Exception:
        return os.getenv(name, "")


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")


@st.cache_resource
def make_supabase_client(url, key):
    return create_client(url, key)


def log_event(client, case_id, user_id, event_type, details):
    client.table("case_events").insert({
        "case_id": case_id,
        "actor_id": user_id,
        "event_type": event_type,
        "details": details,
    }).execute()


def load_memberships(client, user_id):
    result = (
        client.table("hospital_memberships")
        .select("hospital_id, role")
        .eq("user_id", user_id)
        .execute()
    )

    memberships = []

    for membership in result.data:
        hospital_result = (
            client.table("hospitals")
            .select("id, name")
            .eq("id", membership["hospital_id"])
            .limit(1)
            .execute()
        )

        if hospital_result.data:
            hospital = hospital_result.data[0]
            memberships.append({
                "hospital_id": hospital["id"],
                "hospital_name": hospital["name"],
                "role": membership["role"],
            })

    return memberships


def load_cases(client, hospital_id):
    result = (
        client.table("cases")
        .select("*")
        .eq("hospital_id", hospital_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return result.data


def save_event_safely(client, case_id, user_id, event_type, details):
    try:
        log_event(
            client, case_id, user_id, event_type, details
        )
    except Exception:
        st.warning(
            "The case was saved, but its history entry failed. "
            "Contact the administrator before relying on the audit trail."
        )


def login_screen():
    st.title("📋 CashlessReady")
    st.subheader("Hospital staff sign-in")

    st.write(
        "Sign in using an account created by your system administrator."
    )

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign in", type="primary")

    if submit:
        if not SUPABASE_URL or not SUPABASE_KEY:
            st.error("Supabase configuration is missing.")
            return

        try:
            client = make_supabase_client(
                SUPABASE_URL, SUPABASE_KEY
            )
            response = client.auth.sign_in_with_password({
                "email": email.strip(),
                "password": password,
            })

            if not response.user:
                st.error("Sign-in failed.")
                return

            st.session_state["sb_client"] = client
            st.session_state["sb_user_id"] = response.user.id
            st.session_state["sb_email"] = response.user.email
            st.rerun()

        except Exception:
            st.error(
                "Sign-in failed. Check your credentials, account status, "
                "Supabase configuration, and network connection."
            )


if not SUPABASE_URL or not SUPABASE_KEY:
    st.error(
        "Supabase configuration is missing. Add SUPABASE_URL and "
        "SUPABASE_KEY under Streamlit Settings → Secrets."
    )
    st.stop()


if (
    "sb_client" not in st.session_state
    or "sb_user_id" not in st.session_state
):
    login_screen()
    st.stop()


client: Client = st.session_state["sb_client"]
user_id = st.session_state["sb_user_id"]
user_email = st.session_state.get("sb_email", "")

st.title("📋 CashlessReady")
st.caption("Hospital cashless pre-authorisation tracker")

st.warning(
    "Pilot software: use synthetic data only until security, privacy, "
    "backup, and access controls have been fully reviewed and tested. "
    "The checklist is illustrative, not a universal payer requirement."
)

with st.sidebar:
    st.write(f"Signed in: {user_email}")

    if st.button("Sign out"):
        try:
            client.auth.sign_out()
        finally:
            for key in [
                "sb_client", "sb_user_id", "sb_email",
                "selected_hospital_id",
            ]:
                st.session_state.pop(key, None)
            st.rerun()


# Memberships are retrieved from Supabase.
try:
    memberships = load_memberships(client, user_id)
except Exception:
    st.error(
        "Unable to load your hospital access. Ask the administrator "
        "to verify your membership and database policies."
    )
    st.stop()

if not memberships:
    st.error(
        "Your account is not assigned to a hospital yet. "
        "Ask the system administrator to create your hospital membership."
    )
    st.stop()


hospital_options = {
    f'{m["hospital_name"]} — {m["role"]}': m
    for m in memberships
}

selected_label = st.selectbox(
    "Hospital workspace",
    list(hospital_options.keys()),
)

membership = hospital_options[selected_label]
hospital_id = membership["hospital_id"]
role = membership["role"]

# This UI restriction is helpful, but the database RLS policies
# are the actual security boundary.
can_edit = role in ("hospital_admin", "staff")

try:
    cases = load_cases(client, hospital_id)
except Exception:
    st.error(
        "Unable to load cases. Check the Supabase connection "
        "and row-level security policies."
    )
    st.stop()


def missing_documents(case):
    docs = case.get("document_json") or {}
    return [d for d in DOCUMENTS if not docs.get(d, False)]


total = len(cases)
open_count = sum(
    c["status"] != "Discharged / closed" for c in cases
)
query_count = sum(
    c["status"] in ("Query received", "Resubmission pending")
    for c in cases
)
ready_count = sum(
    c["status"] == "Ready for staff review" for c in cases
)

a, b, c, d = st.columns(4)
a.metric("Total cases", total)
b.metric("Open cases", open_count)
c.metric("Queries / resubmissions", query_count)
d.metric("Ready for review", ready_count)

tab_register, tab_form, tab_history = st.tabs([
    "Case register",
    "Create / edit case",
    "Case history",
])


with tab_register:
    st.subheader("Case register")

    search = st.text_input("Search by case label, insurer, or reference")
    status_filter = st.multiselect("Filter by status", STATUSES)

    filtered = []

    for case in cases:
        if status_filter and case["status"] not in status_filter:
            continue

        search_text = " ".join(str(case.get(k) or "") for k in [
            "id", "patient_label", "internal_reference",
            "insurer_tpa", "department", "planned_procedure",
        ]).lower()

        if search.strip().lower() not in search_text:
            continue

        filtered.append(case)

    rows = []

    for case in filtered:
        rows.append({
            "Case ID": case["id"],
            "Case label": case["patient_label"],
            "Reference": case["internal_reference"],
            "Insurer / TPA": case["insurer_tpa"],
            "Procedure": case["planned_procedure"],
            "Admission date": case["planned_admission_date"],
            "Estimate (₹)": case["estimated_amount"],
            "Status": case["status"],
            "Unchecked items": len(missing_documents(case)),
            "Query deadline": case["query_deadline"],
        })

    df = pd.DataFrame(rows)

    if df.empty:
        st.info("No matching cases.")
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Export register as CSV",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="cashlessready_register.csv",
            mime="text/csv",
        )

    st.caption(
        "Only cases returned for the selected hospital are shown. "
        "Database policies must still be tested independently."
    )


with tab_form:
    st.subheader("Create or edit case")

    case_map = {
        f'{c["id"]} — {c["patient_label"]}': c
        for c in cases
    }

    options = ["Create a new case"] + list(case_map.keys())

    selected_case_label = st.selectbox(
        "Choose a case",
        options,
    )

    existing = (
        None if selected_case_label == "Create a new case"
        else case_map[selected_case_label]
    )

    if not can_edit:
        st.info("Your account has view-only access.")
    else:
        existing_docs = (
            (existing or {}).get("document_json") or {}
        )

        with st.form("case_editor"):
            col1, col2 = st.columns(2)

            with col1:
                hospital_name = st.text_input(
                    "Hospital name *",
                    value=membership["hospital_name"],
                    disabled=True,
                )

                reference = st.text_input(
                    "Internal reference",
                    value=(existing or {}).get("internal_reference") or "",
                )

                label = st.text_input(
                    "Non-identifying case label *",
                    value=(existing or {}).get("patient_label") or "",
                )

                insurer = st.text_input(
                    "Insurer / TPA",
                    value=(existing or {}).get("insurer_tpa") or "",
                )

                department = st.text_input(
                    "Department",
                    value=(existing or {}).get("department") or "",
                )

            with col2:
                procedure = st.text_input(
                    "Planned procedure",
                    value=(existing or {}).get("planned_procedure") or "",
                )

                admission = st.text_input(
                    "Planned admission date (YYYY-MM-DD)",
                    value=str(
                        (existing or {}).get("planned_admission_date") or ""
                    ),
                )

                amount = st.number_input(
                    "Estimated amount (₹)",
                    min_value=0.0,
                    step=1000.0,
                    value=float(
                        (existing or {}).get("estimated_amount") or 0
                    ),
                )

                current_status = (existing or {}).get("status", "Draft")

                status = st.selectbox(
                    "Status",
                    STATUSES,
                    index=STATUSES.index(current_status),
                )

                deadline = st.text_input(
                    "Query deadline (YYYY-MM-DD)",
                    value=str((existing or {}).get("query_deadline") or ""),
                )

            query_notes = st.text_area(
                "Query notes (no patient identifiers)",
                value=(existing or {}).get("query_notes") or "",
            )

            staff_notes = st.text_area(
                "Administrative notes (no patient identifiers)",
                value=(existing or {}).get("staff_notes") or "",
            )

            st.markdown("**Document checklist**")

            docs = {}

            doc_cols = st.columns(2)

            for i, document in enumerate(DOCUMENTS):
                with doc_cols[i % 2]:
                    docs[document] = st.checkbox(
                        document,
                        value=bool(existing_docs.get(document, False)),
                        key=f'doc_{existing["id"] if existing else "new"}_{i}',
                    )

            save = st.form_submit_button("Save case", type="primary")

        if save:
            if not label.strip():
                st.error("A non-identifying case label is required.")
                st.stop()

            if admission.strip():
                try:
                    date.fromisoformat(admission.strip())
                except ValueError:
                    st.error("Admission date must use YYYY-MM-DD.")
                    st.stop()

            if deadline.strip():
                try:
                    date.fromisoformat(deadline.strip())
                except ValueError:
                    st.error("Query deadline must use YYYY-MM-DD.")
                    st.stop()

            payload = {
                "hospital_id": hospital_id,
                "internal_reference": reference.strip() or None,
                "patient_label": label.strip(),
                "insurer_tpa": insurer.strip() or None,
                "department": department.strip() or None,
                "planned_procedure": procedure.strip() or None,
                "planned_admission_date": admission.strip() or None,
                "estimated_amount": float(amount),
                "status": status,
                "query_deadline": deadline.strip() or None,
                "query_notes": query_notes.strip() or None,
                "staff_notes": staff_notes.strip() or None,
                "document_json": docs,
            }

            try:
                if existing:
                    result = (
                        client.table("cases")
                        .update(payload)
                        .eq("id", existing["id"])
                        .eq("hospital_id", hospital_id)
                        .execute()
                    )

                    if not result.data:
                        st.error(
                            "No case was updated. Check your access "
                            "or reload the register."
                        )
                        st.stop()

                    case_id = existing["id"]
                    event_type = "Case updated"

                else:
                    payload["created_by"] = user_id

                    result = (
                        client.table("cases")
                        .insert(payload)
                        .execute()
                    )

                    if not result.data:
                        st.error("Case creation failed.")
                        st.stop()

                    case_id = result.data[0]["id"]
                    event_type = "Case created"

                save_event_safely(
                    client,
                    case_id,
                    user_id,
                    event_type,
                    f"Status: {status}",
                )

                st.success("Case saved.")
                st.rerun()

            except Exception:
                st.error(
                    "The case could not be saved. Check your hospital "
                    "membership, RLS policies, and database connection."
                )


with tab_history:
    st.subheader("Case history")

    if not cases:
        st.info("Create a case to view its history.")
    else:
        history_map = {
            f'{c["id"]} — {c["patient_label"]}': c["id"]
            for c in cases
        }

        history_label = st.selectbox(
            "Select case history",
            list(history_map.keys()),
        )

        history_id = history_map[history_label]

        try:
            events = (
                client.table("case_events")
                .select("event_time, actor_id, event_type, details")
                .eq("case_id", history_id)
                .order("event_time", desc=True)
                .execute()
            )

            if events.data:
                st.dataframe(
                    pd.DataFrame(events.data),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("No history entries available.")

        except Exception:
            st.error("Unable to retrieve the case history.")


st.divider()

st.caption(
    "CashlessReady pilot | Supabase storage | Hospital-specific access | "
    "Not yet approved for production patient data."
)

   
