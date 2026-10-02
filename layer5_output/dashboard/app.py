import streamlit as st
import requests

st.set_page_config(
    page_title="VN Labor Market Intelligence",
    page_icon="📊",
    layout="wide"
)

st.title("VN Labor Market Intelligence Dashboard")
st.markdown("Welcome to the Labor Market Intelligence Dashboard for the Finance & Accounting Industry.")

API_BASE = "http://localhost:8000"

# Sidebar: Filters
with st.sidebar:
    st.header("Global Filters")
    industry = st.selectbox("Ngành (Industry)", ["Tài chính - Kế toán", "IT", "Marketing"])
    role = st.selectbox("Vị trí (Role)", ["Kế toán tổng hợp", "Kế toán thuế", "FP&A", "Investment Analyst"])
    region = st.multiselect("Khu vực (Region)", ["HCM", "Hà Nội", "Đà Nẵng"])
    level = st.multiselect("Cấp bậc (Level)", ["Intern", "Staff", "Senior", "Manager"])
    months = st.slider("Số tháng dữ liệu (Months of data)", 1, 12, 3)

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Minimum JD", 
    "💰 Benefits Compare", 
    "📈 Xu hướng",
    "🔍 Gap Analysis"
])

with tab1:
    st.header(f"Minimum Viable JD for {role}")
    st.info("API integration pending. This will display the mandatory and preferred skills.")
    # Example placeholder
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Bắt buộc (Mandatory) >= 60%")
        st.write("- Excel nâng cao (90%)")
        st.write("- Kế toán tổng hợp (85%)")
    with col2:
        st.subheader("Ưu tiên (Preferred) 30-60%")
        st.write("- ERP / SAP (55%)")
        st.write("- Tiếng Anh (45%)")

with tab2:
    st.header("Benefits Comparison")
    st.info("API integration pending. Heatmap of benefits by company type/level.")

with tab3:
    st.header("Skill Trends over time")
    skill_input = st.text_input("Enter a skill to track:", "Python")
    if st.button("Check Trend"):
        st.write(f"Showing trend for {skill_input}...")

with tab4:
    st.header("Candidate Gap Analysis")
    st.text_area("Paste Candidate CV / Skills here:")
    if st.button("Analyze Gap"):
        st.success("Gap analysis results will appear here.")
