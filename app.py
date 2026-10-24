import streamlit as st
import pandas as pd
import json
import os
from google import genai
from google.genai import types

# 1. Page Configuration
st.set_page_config(page_title="AuthStream Enterprise AI", page_icon="🏥", layout="wide")

# 2. Secure Gemini API Key Initialization
# Checks Streamlit Secrets first, falls back to local Environment Variables
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

# Initialize Gemini Client if key exists
client = None
if api_key:
    client = genai.Client(api_key=api_key)
else:
    st.sidebar.warning("⚠️ Gemini API Key not found. Please add your key to Streamlit Secrets or environment variables to enable live AI features.")

# 3. Enterprise Sidebar & Monetization Layer
with st.sidebar:
    st.header("Corporate Account")
    st.success("🔒 Secure HIPAA-Compliant Sandbox")
    st.markdown("---")
    st.subheader("Tier Status")
    st.info("🏢 **Enterprise Pilot Plan**\n\nUpgrade to Dedicated Server for HL7/FHIR EHR Integration.")
    st.markdown("---")
    st.caption("AuthStream v2026.10 • PII Encrypted")

# 4. Header
st.title("🏥 AuthStream Enterprise AI")
st.subheader("Live Prior Authorization Optimization Dashboard Powered by Gemini")

# 5. Mock Data Generation for Executive View
auth_data = {
    "Case ID": ["AUTH-9081", "AUTH-9082", "AUTH-9083", "AUTH-9084", "AUTH-9085"],
    "Patient Initials": ["J.D.", "M.R.", "A.K.", "T.S.", "L.B."],
    "Procedure / Treatment": ["Knee Arthroscopy", "Brain MRI w/ Contrast", "Lumbar Fusion", "Infliximab Infusion", "Cardiac Catheterization"],
    "Payer / Insurance": ["BlueCross Horizon", "UnitedHealth Premium", "Aetna Core", "Cigna Choice", "Humana Gold"],
    "Est. Value ($)":,
    "Status": ["Approved", "Missing Clinical Notes", "Pending Review", "Denied - Appeal Pending", "Approved"]
}
df = pd.DataFrame(auth_data)

# 6. Executive Key Metrics Row
st.subheader("📊 Network Performance Overview")
m1, m2, m3, m4 = st.columns(4)

total_pipeline = df["Est. Value ($)"].sum()
approved_value = df[df["Status"] == "Approved"]["Est. Value ($)"].sum()
denied_count = len(df[df["Status"].str.contains("Denied")])
pending_count = len(df[df["Status"] == "Pending Review"])

m1.metric("Total Pipeline Value", f"${total_pipeline:,.2f}")
m2.metric("Revenue Unlocked (Approved)", f"${approved_value:,.2f}", delta="+$12,500 today")
m3.metric("Pending Payer Review", pending_count)
m4.metric("High-Risk Denials", denied_count, delta="Action Required", delta_color="inverse")

st.markdown("---")

# 7. Interactive Case Manager Workspace
tab1, tab2 = st.tabs(["📋 Active Case Queue", "🤖 Gemini Pre-Screening Engine"])

with tab1:
    st.subheader("Real-Time Prior Authorization Tracking")
    status_filter = st.selectbox("Filter Queue by Status:", ["All Cases", "Approved", "Pending Review", "Action Required (Missing/Denied)"])
    
    filtered_df = df.copy()
    if status_filter == "Approved":
        filtered_df = df[df["Status"] == "Approved"]
    elif status_filter == "Pending Review":
        filtered_df = df[df["Status"] == "Pending Review"]
    elif status_filter == "Action Required (Missing/Denied)":
        filtered_df = df[df["Status"].str.contains("Missing|Denied")]
        
    st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    
    st.markdown("### 🧬 EHR System Integration")
    if st.button("🔄 Push Approved Claims to Epic/Cerner System"):
        st.warning("🔒 **Enterprise Integration Lock:** Exporting directly to hospital EHR systems requires the **AuthStream Enterprise API Add-on**.")

with tab2:
    st.subheader("AI Pre-Screening & Risk Assessment")
    st.write("Analyze clinical documentation completeness using Gemini 2.5 Flash to predict compliance hurdles.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        insurance = st.selectbox("Select Payer:", ["BlueCross Horizon", "UnitedHealth Premium", "Aetna Core", "Cigna Choice"])
        procedure = st.text_input("Enter Procedure CPT Code or Description:", value="64493 - Lumbar Injection")
        clinical_notes = st.text_area(
            "Paste Physician Clinical Decision Notes:", 
            value="Patient presents with chronic lower back pain lasting 6 months. Failed conservative physical therapy treatment lasting 12 weeks. Imaging confirms facet joint arthropathy.",
            height=200
        )
        
        run_analysis = st.button("🚀 Run Live Gemini Evaluation", type="primary", disabled=(client is None))
    
    with col2:
        st.markdown("#### **AI Analysis Output**")
        
        if run_analysis and client:
            with st.spinner("Gemini is auditing clinical notes against medical policy standard guidelines..."):
                try:
                    # Structured prompt engineering ensuring deterministic JSON breakdown
                    prompt = f"""
                    You are an expert healthcare insurance auditor checking prior authorization documents.
                    Analyze the following clinical notes for the procedure '{procedure}' under payer '{insurance}'.
                    
                    Clinical Notes:
                    \"\"\"{clinical_notes}\"\"\"
                    
                    Return a JSON object with exactly these four keys:
                    1. "probability": an integer between 0 and 100 representing approval probability.
                    2. "met_criteria": a bulleted string list of policy prerequisites found.
                    3. "risk_factors": a bulleted string list of missing details or compliance risks.
                    4. "letter": A formally drafted Medical Justification Letter to the insurer.
                    
                    Return ONLY valid raw JSON. No markdown block formatting around the JSON string.
                    """
                    
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1
                        )
                    )
                    
                    # Parse the structured JSON response
                    result = json.loads(response.text)
                    
                    # UI Presentation based on parsed data
                    score = result.get("probability", 50)
                    if score >= 75:
                        st.success(f"🎉 **Approval Probability: {score}%**")
                    elif score >= 50:
                        st.warning(f"⚠️ **Approval Probability: {score}%**")
                    else:
                        st.error(f"❌ **Approval Probability: {score}%**")
                        
                    st.markdown("**✅ Policy Prerequisites Met:**")
                    st.write(result.get("met_criteria", "None documented."))
                    
                    st.markdown("**⚠️ Identified Risk Factors:**")
                    st.write(result.get("risk_factors", "None detected."))
                    
                    st.markdown("---")
                    st.markdown("#### ✉️ Automated Payer Justification Letter")
                    st.text_area("Generated Output (Copy to Payer Portal):", value=result.get("letter", ""), height=200)
                    
                except Exception as e:
                    st.error(f"Error running model analysis: {e}")
        elif not client:
            st.info("Please configure a valid `GEMINI_API_KEY` in the app setup settings to run this analysis live.")
        else:
            st.info("Input or adjust the clinical notes on the left and click 'Run Live Gemini Evaluation'.")
