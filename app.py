
import os
import json
import streamlit as st
import pandas as pd
from google import genai
from google.genai import types


# ============================================================
# 1. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AuthStream Enterprise AI",
    page_icon="🏥",
    layout="wide"
)


# ============================================================
# 2. API KEY AND GEMINI CLIENT
# ============================================================

def get_api_key():
    """Read API key from Streamlit Secrets or environment."""
    key = os.environ.get("GEMINI_API_KEY")

    if key:
        return key

    try:
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None


api_key = get_api_key()
client = None

if api_key:
    try:
        client = genai.Client(api_key=api_key)
    except Exception:
        client = None


# ============================================================
# 3. SESSION STATE
# ============================================================

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "analysis_error" not in st.session_state:
    st.session_state.analysis_error = None

if "last_analysis_input" not in st.session_state:
    st.session_state.last_analysis_input = None


# ============================================================
# 4. MOCK AUTHORIZATION DATA
# ============================================================

auth_data = {
    "Case ID": [
        "AUTH-9081",
        "AUTH-9082",
        "AUTH-9083",
        "AUTH-9084",
        "AUTH-9085"
    ],
    "Patient Initials": [
        "J.D.", "M.R.", "A.K.", "T.S.", "L.B."
    ],
    "Procedure / Treatment": [
        "Knee Arthroscopy",
        "Brain MRI with Contrast",
        "Lumbar Fusion",
        "Infliximab Infusion",
        "Cardiac Catheterization"
    ],
    "Payer / Insurance": [
        "BlueCross Horizon",
        "UnitedHealth Premium",
        "Aetna Core",
        "Cigna Choice",
        "Humana Gold"
    ],
    "Est. Value ($)": [
        8500, 1200, 18000, 6500, 12000
    ],
    "Status": [
        "Approved",
        "Missing Clinical Notes",
        "Pending Review",
        "Denied - Appeal Pending",
        "Approved"
    ]
}

df = pd.DataFrame(auth_data)


# ============================================================
# 5. SIDEBAR
# ============================================================

with st.sidebar:
    st.header("Corporate Account")

    st.caption(
        "Demonstration environment — mock data only."
    )

    st.markdown("---")
    st.subheader("Tier Status")

    st.info(
        "**Enterprise Pilot**\n\n"
        "Future capabilities: payer-policy rules, "
        "audit trails, role-based access and authorized "
        "EHR integrations."
    )

    st.markdown("---")

    if client:
        st.success("Gemini client initialized")
    else:
        st.warning(
            "Gemini API key not configured. "
            "AI analysis is unavailable."
        )

    st.caption(
        "AuthStream prototype | No compliance certification implied"
    )


# ============================================================
# 6. HEADER
# ============================================================

st.title("🏥 AuthStream Enterprise AI")

st.subheader(
    "Prior Authorization Tracking & "
    "AI-Assisted Documentation Review"
)

st.warning(
    "Demonstration only. Use synthetic data. "
    "AI findings require human verification and do not "
    "establish medical necessity, payer approval, or "
    "regulatory compliance."
)


# ============================================================
# 7. EXECUTIVE METRICS
# ============================================================

st.subheader("📊 Network Performance Overview")

m1, m2, m3, m4 = st.columns(4)

total_pipeline = df["Est. Value ($)"].sum()

approved_value = df.loc[
    df["Status"].eq("Approved"),
    "Est. Value ($)"
].sum()

denied_count = int(
    df["Status"].str.contains(
        "Denied", case=False, na=False
    ).sum()
)

pending_count = int(
    df["Status"].eq("Pending Review").sum()
)

m1.metric(
    "Total Pipeline Value",
    f"${total_pipeline:,.0f}"
)

m2.metric(
    "Value of Approved Cases",
    f"${approved_value:,.0f}"
)

m3.metric(
    "Pending Payer Review",
    pending_count
)

m4.metric(
    "Cases Marked Denied",
    denied_count
)

st.caption(
    "All values above use illustrative demonstration records. "
    "Approved case value is not necessarily collected revenue."
)

st.divider()


# ============================================================
# 8. TABS
# ============================================================

tab1, tab2 = st.tabs([
    "📋 Active Case Queue",
    "🤖 Gemini Documentation Review"
])


# ============================================================
# 9. CASE QUEUE
# ============================================================

with tab1:

    st.subheader("Prior Authorization Case Tracker")

    status_filter = st.selectbox(
        "Filter queue by status",
        [
            "All Cases",
            "Approved",
            "Pending Review",
            "Action Required (Missing/Denied)"
        ]
    )

    filtered_df = df.copy()

    if status_filter == "Approved":
        filtered_df = df[
            df["Status"].eq("Approved")
        ]

    elif status_filter == "Pending Review":
        filtered_df = df[
            df["Status"].eq("Pending Review")
        ]

    elif status_filter == "Action Required (Missing/Denied)":
        filtered_df = df[
            df["Status"].str.contains(
                "Missing|Denied",
                case=False,
                na=False
            )
        ]

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "Download Case Queue CSV",
        data=filtered_df.to_csv(index=False).encode("utf-8"),
        file_name="authstream_case_queue.csv",
        mime="text/csv"
    )

    st.markdown("### EHR Integration")

    if st.button("Check EHR Integration Status"):
        st.info(
            "No EHR connection is configured. "
            "This prototype does not transmit claims or "
            "patient records to Epic, Cerner, or other EHRs."
        )


# ============================================================
# 10. GEMINI DOCUMENTATION REVIEW
# ============================================================

with tab2:

    st.subheader("AI-Assisted Documentation Review")

    st.write(
        "Review supplied documentation for potentially "
        "missing information. Findings are suggestions "
        "for human review, not verified payer requirements."
    )

    with st.form("documentation_review_form"):

        insurance = st.selectbox(
            "Select demonstration payer",
            [
                "BlueCross Horizon",
                "UnitedHealth Premium",
                "Aetna Core",
                "Cigna Choice"
            ]
        )

        procedure = st.text_input(
            "Procedure / CPT code",
            value="64493 - Lumbar injection"
        )

        clinical_notes = st.text_area(
            "Clinical documentation",
            value=(
                "Synthetic demonstration case: "
                "Patient has chronic lower back pain for "
                "6 months. The notes report 12 weeks of "
                "conservative physical therapy without "
                "adequate improvement. Imaging reportedly "
                "shows facet joint arthropathy. "
                "Verify all facts against the actual record."
            ),
            height=220
        )

        submitted = st.form_submit_button(
            "Run Documentation Review",
            type="primary",
            disabled=(client is None)
        )

    if submitted:

        st.session_state.analysis_result = None
        st.session_state.analysis_error = None

        if not procedure.strip():
            st.session_state.analysis_error = (
                "Please enter a procedure or CPT code."
            )

        elif not clinical_notes.strip():
            st.session_state.analysis_error = (
                "Please enter the documentation to review."
            )

        elif len(clinical_notes) > 20000:
            st.session_state.analysis_error = (
                "The input exceeds the 20,000-character limit."
            )

        elif client is None:
            st.session_state.analysis_error = (
                "Gemini is unavailable. Configure GEMINI_API_KEY."
            )

        else:
            prompt = f"""
You assist a human healthcare authorization reviewer.

This is a documentation completeness review, NOT a
medical decision, medical necessity determination, or
prediction of insurer approval.

Payer label supplied by user: {insurance}
Procedure supplied by user: {procedure}

Documentation supplied:
<documentation>
{clinical_notes}
</documentation>

Instructions:
- Use only facts contained in the supplied documentation.
- Do not invent patient facts or claim to know a payer's
  current policy unless that policy is supplied and verified.
- Distinguish documented facts from information that is absent.
- Suggest questions a human reviewer should investigate.
- Do not make up a probability of approval.
- The draft letter must contain placeholders for any
  unverified facts and must be checked by a qualified
  professional before submission.

Return a JSON object with exactly these keys:
{{
  "readiness": "Needs review",
  "documented_facts": ["fact supported by supplied text"],
  "missing_information": ["information not found in supplied text"],
  "review_flags": ["issue requiring human verification"],
  "suggested_next_steps": ["practical verification step"],
  "letter": "Draft letter with placeholders where needed"
}}

The readiness field must be one of:
"Documentation appears more complete",
"Needs review",
"Insufficient information".

Return valid JSON only.
"""

            try:
                with st.spinner(
                    "Reviewing documentation with Gemini..."
                ):
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )

                if not response.text:
                    raise ValueError(
                        "The model returned an empty response."
                    )

                result = json.loads(response.text)

                required_keys = [
                    "readiness",
                    "documented_facts",
                    "missing_information",
                    "review_flags",
                    "suggested_next_steps",
                    "letter"
                ]

                if not isinstance(result, dict):
                    raise ValueError(
                        "The model response is not a JSON object."
                    )

                missing_keys = [
                    key for key in required_keys
                    if key not in result
                ]

                if missing_keys:
                    raise ValueError(
                        "The response is missing required fields: "
                        + ", ".join(missing_keys)
                    )

                allowed_readiness = [
                    "Documentation appears more complete",
                    "Needs review",
                    "Insufficient information"
                ]

                if result["readiness"] not in allowed_readiness:
                    raise ValueError(
                        "The model returned an invalid readiness label."
                    )

                list_fields = [
                    "documented_facts",
                    "missing_information",
                    "review_flags",
                    "suggested_next_steps"
                ]

                for field in list_fields:
                    if not isinstance(result[field], list):
                        raise ValueError(
                            f"The field '{field}' must be a list."
                        )

                if not isinstance(result["letter"], str):
                    raise ValueError(
                        "The draft letter must be text."
                    )

                st.session_state.analysis_result = result

            except json.JSONDecodeError:
                st.session_state.analysis_error = (
                    "The AI response was not valid JSON. "
                    "Please retry."
                )

            except Exception as exc:
                st.session_state.analysis_error = (
                    "The review failed. Check your API key, "
                    "model availability, quota and connection. "
                    f"Technical detail: {str(exc)[:500]}"
                )

    # Display errors outside the form submission block.
    if st.session_state.analysis_error:
        st.error(st.session_state.analysis_error)

    # Display saved results after Streamlit reruns.
    result = st.session_state.analysis_result

    if result:

        st.divider()
        st.markdown("### AI Review Results")

        readiness = result["readiness"]

        if readiness == "Documentation appears more complete":
            st.success(readiness)

        elif readiness == "Needs review":
            st.warning(readiness)

        else:
            st.error(readiness)

        st.caption(
            "This label is an AI-generated preliminary assessment, "
            "not a verified payer-policy decision."
        )

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### Documented facts")
            st.write(result["documented_facts"])

            st.markdown("#### Missing information")
            st.write(result["missing_information"])

        with col2:
            st.markdown("#### Review flags")
            st.write(result["review_flags"])

            st.markdown("#### Suggested next steps")
            st.write(result["suggested_next_steps"])

        st.markdown("---")
        st.markdown("### Draft Justification Letter")

        st.text_area(
            "Review and edit before use",
            value=result["letter"],
            height=300,
            key="generated_letter"
        )

        st.download_button(
            "Download Draft Letter",
            data=result["letter"].encode("utf-8"),
            file_name="authorization_letter_draft.txt",
            mime="text/plain"
        )

        st.info(
            "A qualified reviewer must verify every factual claim, "
            "clinical statement and applicable payer requirement "
            "before the draft is used."
        )

    elif client is None:
        st.info(
            "Add GEMINI_API_KEY to Streamlit Secrets or your "
            "local environment variables to enable live AI review."
        )

    else:
        st.caption(
            "Submit the form above to run a documentation review."
        )
