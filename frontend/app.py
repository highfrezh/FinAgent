import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────
API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="FinAgent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Helper Functions ──────────────────────────────────────────────────────────

def api_get(endpoint: str) -> dict:
    try:
        response = requests.get(f"{API_BASE}{endpoint}", timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return {}


def api_post(endpoint: str, data: dict = None, files=None) -> dict:
    try:
        if files:
            response = requests.post(
                f"{API_BASE}{endpoint}", files=files, timeout=60
            )
        else:
            response = requests.post(
                f"{API_BASE}{endpoint}", json=data, timeout=60
            )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return {}


def status_badge(status: str) -> str:
    colors = {
        "valid": "🟢",
        "approved": "✅",
        "flagged": "🔴",
        "rejected": "⛔",
        "processing": "🔵",
        "pending": "⚪",
    }
    return f"{colors.get(status.lower(), '⚪')} {status.upper()}"


def format_currency(amount: float, currency: str = "USD") -> str:
    if amount is None:
        return "N/A"
    symbols = {"USD": "$", "NGN": "₦", "EUR": "€", "GBP": "£"}
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{amount:,.2f}"


# ── Sidebar Navigation ────────────────────────────────────────────────────────

st.sidebar.image("https://img.icons8.com/fluency/96/robot.png", width=80)
st.sidebar.title("FinAgent")
st.sidebar.caption("Autonomous Finance Operations")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["📊 Overview", "📋 Invoice Queue", "📄 All Invoices",
     "📈 Reports", "🏢 Vendors", "⬆️ Upload Invoice"]
)

st.sidebar.divider()
st.sidebar.caption(f"API: {API_BASE}")
st.sidebar.caption(f"Updated: {datetime.now().strftime('%H:%M:%S')}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

if page == "📊 Overview":
    st.title("📊 FinAgent Overview")
    st.caption("Real-time finance operations dashboard")

    # Queue stats
    stats = api_get("/queue/stats/summary")
    report = api_get("/reports/monthly?days=30")

    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "🔴 Pending Review",
                stats.get("pending_review", 0),
                help="Flagged invoices waiting for human approval"
            )
        with col2:
            st.metric(
                "✅ Approved",
                stats.get("approved_today", 0),
                help="Invoices approved"
            )
        with col3:
            st.metric(
                "⛔ Rejected",
                stats.get("rejected_today", 0),
                help="Invoices rejected"
            )
        with col4:
            st.metric(
                "💰 Amount Pending",
                format_currency(stats.get("total_amount_pending", 0)),
                help="Total value of invoices pending review"
            )

    st.divider()

    if report:
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("📋 Invoice Status Breakdown")
            status = report.get("status_summary", {})
            if status:
                status_df = pd.DataFrame({
                    "Status": ["Valid", "Flagged", "Approved",
                               "Rejected", "Processing", "Pending"],
                    "Count": [
                        status.get("valid", 0),
                        status.get("flagged", 0),
                        status.get("approved", 0),
                        status.get("rejected", 0),
                        status.get("processing", 0),
                        status.get("pending", 0),
                    ]
                })
                status_df = status_df[status_df["Count"] > 0]
                st.bar_chart(status_df.set_index("Status"))

        with col2:
            st.subheader("🏢 Top Vendors by Spend")
            vendors = report.get("top_vendors", [])
            if vendors:
                vendor_df = pd.DataFrame([
                    {
                        "Vendor": v["vendor_name"],
                        "Total Spend": v["total_spend"],
                        "Invoices": v["invoice_count"],
                        "Flagged": v["flagged_count"]
                    }
                    for v in vendors[:5]
                ])
                st.dataframe(vendor_df, use_container_width=True)

        st.divider()
        st.subheader("🤖 AI Narrative")
        narrative = report.get("narrative", "")
        if narrative:
            st.info(narrative)

        recommendations = report.get("recommendations", [])
        if recommendations:
            st.subheader("💡 Recommendations")
            for rec in recommendations:
                st.warning(f"→ {rec}")

        st.divider()
        st.subheader("🚨 Anomaly Summary")
        anomaly = report.get("anomaly_summary", {})
        if anomaly:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Anomalies", anomaly.get("total_anomalies", 0))
                st.metric("High Velocity", anomaly.get("high_velocity_count", 0))
            with col2:
                st.metric("Duplicate Amounts", anomaly.get("duplicate_amount_count", 0))
                st.metric("Amount Spikes", anomaly.get("amount_spike_count", 0))
            with col3:
                st.metric("Round Numbers", anomaly.get("round_number_count", 0))
                st.metric("Off Hours", anomaly.get("off_hours_count", 0))


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — INVOICE QUEUE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📋 Invoice Queue":
    st.title("📋 Approval Queue")
    st.caption("Flagged invoices waiting for human review")

    queue = api_get("/queue/")
    total = queue.get("total", 0)
    items = queue.get("items", [])

    st.metric("Invoices Pending Review", total)
    st.divider()

    if not items:
        st.success("✅ Queue is empty — no invoices pending review")
    else:
        for item in items:
            with st.expander(
                f"🔴 {item.get('vendor_name', 'Unknown')} — "
                f"{format_currency(item.get('amount'), item.get('currency', 'USD'))} — "
                f"Score: {item.get('anomaly_score', 0):.2f}"
            ):
                col1, col2 = st.columns(2)

                with col1:
                    st.write("**Invoice Details**")
                    st.write(f"Invoice #: `{item.get('invoice_number', 'N/A')}`")
                    st.write(f"Vendor: `{item.get('vendor_name', 'N/A')}`")
                    st.write(f"Amount: `{format_currency(item.get('amount'), item.get('currency', 'USD'))}`")
                    st.write(f"File: `{item.get('file_name', 'N/A')}`")

                with col2:
                    st.write("**AI Findings**")
                    anomaly_flags = item.get("anomaly_flags", [])
                    if anomaly_flags:
                        for flag in anomaly_flags:
                            st.error(f"🚨 {flag}")
                    else:
                        st.info("No anomaly flags")

                    validation = item.get("validation_result", {})
                    if validation:
                        val_flags = validation.get("flags", [])
                        for flag in val_flags:
                            st.warning(f"⚠️ {flag}")

                st.write("**Take Action**")
                action_col1, action_col2 = st.columns(2)

                with action_col1:
                    with st.form(key=f"approve_{item['id']}"):
                        approver = st.text_input(
                            "Your email", key=f"approver_{item['id']}"
                        )
                        comment = st.text_area(
                            "Comment (optional)", key=f"comment_{item['id']}"
                        )
                        if st.form_submit_button("✅ Approve", type="primary"):
                            if approver:
                                result = api_post(
                                    f"/queue/{item['id']}/approve",
                                    {"approved_by": approver, "comment": comment}
                                )
                                if result:
                                    st.success("Invoice approved successfully")
                                    st.rerun()
                            else:
                                st.error("Please enter your email")

                with action_col2:
                    with st.form(key=f"reject_{item['id']}"):
                        rejecter = st.text_input(
                            "Your email", key=f"rejecter_{item['id']}"
                        )
                        reason = st.text_area(
                            "Reason (required)", key=f"reason_{item['id']}"
                        )
                        if st.form_submit_button("⛔ Reject", type="secondary"):
                            if rejecter and reason:
                                result = api_post(
                                    f"/queue/{item['id']}/reject",
                                    {"rejected_by": rejecter, "reason": reason}
                                )
                                if result:
                                    st.success("Invoice rejected")
                                    st.rerun()
                            else:
                                st.error("Please enter email and reason")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — ALL INVOICES
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📄 All Invoices":
    st.title("📄 All Invoices")

    data = api_get("/invoices/?limit=50")
    invoices = data.get("invoices", [])
    total = data.get("total", 0)

    st.metric("Total Invoices", total)

    if invoices:
        df = pd.DataFrame([
            {
                "Invoice #": inv.get("invoice_number", "N/A"),
                "Vendor": inv.get("vendor_name", "N/A"),
                "Amount": inv.get("amount", 0),
                "Currency": inv.get("currency", "USD"),
                "Status": inv.get("status", "").upper(),
                "Created": inv.get("created_at", "")[:10],
            }
            for inv in invoices
        ])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No invoices found")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — REPORTS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📈 Reports":
    st.title("📈 Finance Report")

    days = st.slider("Report period (days)", 7, 365, 30)

    if st.button("Generate Report", type="primary"):
        with st.spinner("Generating report..."):
            report = api_get(f"/reports/monthly?days={days}")

        if report:
            st.success(f"Report generated for last {days} days")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(
                    "Total Spend",
                    format_currency(report.get("total_spend", 0))
                )
            with col2:
                status = report.get("status_summary", {})
                st.metric("Total Invoices", status.get("total_invoices", 0))
            with col3:
                st.metric("Flagged", status.get("flagged", 0))

            st.divider()

            monthly = report.get("monthly_spend", [])
            if monthly:
                st.subheader("📅 Monthly Spend Trend")
                monthly_df = pd.DataFrame(monthly)
                st.line_chart(monthly_df.set_index("month")["total_spend"])

            st.divider()

            vendors = report.get("top_vendors", [])
            if vendors:
                st.subheader("🏢 Vendor Breakdown")
                vendor_df = pd.DataFrame([
                    {
                        "Vendor": v["vendor_name"],
                        "Total Spend": format_currency(v["total_spend"]),
                        "Invoices": v["invoice_count"],
                        "Average": format_currency(v["average_amount"]),
                        "Flagged": v["flagged_count"]
                    }
                    for v in vendors
                ])
                st.dataframe(vendor_df, use_container_width=True)

            st.divider()

            st.subheader("🤖 AI Narrative")
            st.info(report.get("narrative", ""))

            recommendations = report.get("recommendations", [])
            if recommendations:
                st.subheader("💡 Recommendations")
                for rec in recommendations:
                    st.warning(f"→ {rec}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — VENDORS
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🏢 Vendors":
    st.title("🏢 Vendor Registry")

    vendors = api_get("/vendors/")

    if vendors:
        df = pd.DataFrame([
            {
                "Name": v["name"],
                "Email": v.get("email", "N/A"),
                "Verified": "✅" if v["is_verified"] else "❌",
                "Active": "✅" if v["is_active"] else "❌",
                "Total Invoices": v["total_invoices"],
                "Total Spend": format_currency(v["total_spend"]),
                "Avg Invoice": format_currency(v["average_invoice_amount"]),
            }
            for v in vendors
        ])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No vendors registered yet")

    st.divider()
    st.subheader("Register New Vendor")

    with st.form("register_vendor"):
        name = st.text_input("Vendor Name *")
        email = st.text_input("Email")
        tax_id = st.text_input("Tax ID")
        payment_terms = st.number_input(
            "Payment Terms (days)", min_value=1, max_value=120, value=30
        )

        if st.form_submit_button("Register Vendor", type="primary"):
            if name:
                result = api_post("/vendors/", {
                    "name": name,
                    "email": email or None,
                    "tax_id": tax_id or None,
                    "payment_terms_days": payment_terms,
                    "categories": []
                })
                if result:
                    st.success(f"Vendor '{name}' registered successfully")
                    st.rerun()
            else:
                st.error("Vendor name is required")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — UPLOAD INVOICE
# ══════════════════════════════════════════════════════════════════════════════

elif page == "⬆️ Upload Invoice":
    st.title("⬆️ Upload Invoice")
    st.caption("Upload a PDF or paste invoice text for processing")

    tab1, tab2 = st.tabs(["📄 Upload PDF", "📝 Paste Text"])

    with tab1:
        uploaded_file = st.file_uploader(
            "Choose a PDF invoice", type=["pdf"]
        )
        if uploaded_file:
            st.info(f"File selected: {uploaded_file.name}")
            if st.button("Process PDF", type="primary"):
                with st.spinner("Processing invoice through AI agents..."):
                    files = {"file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        "application/pdf"
                    )}
                    result = api_post("/invoices/upload", files=files)

                if result:
                    st.success("Invoice processed successfully")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Vendor", result.get("vendor_name", "N/A"))
                    with col2:
                        st.metric(
                            "Amount",
                            format_currency(
                                result.get("amount"),
                                result.get("currency", "USD")
                            )
                        )
                    with col3:
                        st.metric("Status", status_badge(result.get("status", "")))
                    st.json(result)

    with tab2:
        invoice_text = st.text_area(
            "Paste invoice text here",
            height=300,
            placeholder="INVOICE\n\nFrom: Vendor Name\nInvoice #: INV-001\n..."
        )
        if st.button("Process Text", type="primary"):
            if invoice_text.strip():
                with st.spinner("Processing invoice through AI agents..."):
                    result = requests.post(
                        f"{API_BASE}/invoices/text",
                        params={"raw_text": invoice_text},
                        timeout=60
                    ).json()

                if result:
                    st.success("Invoice processed successfully")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Vendor", result.get("vendor_name", "N/A"))
                    with col2:
                        st.metric(
                            "Amount",
                            format_currency(
                                result.get("amount"),
                                result.get("currency", "USD")
                            )
                        )
                    with col3:
                        st.metric("Status", status_badge(result.get("status", "")))
                    st.json(result)
            else:
                st.error("Please paste some invoice text")