"""
Streamlit Application: Financial Reconciliation Pipeline
Module 1: Data Import and Validation
Module 2: Intelligent Transaction Matching
Module 3: Match Review and Reconciliation
Module 4: Dashboard, Reporting, and Evaluation
"""

import os
import uuid
import io
from decimal import Decimal
import pandas as pd
import streamlit as st
from datetime import datetime, timezone

from validator import validate_records, map_columns, INVOICE_COLUMN_ALIASES, PAYMENT_COLUMN_ALIASES
from matcher import IntelligentTransactionMatcher
from reconciliation import to_decimal, ReconciliationEngine
from evaluation import ReconciliationEvaluator, ReportGenerator, DEFAULT_GROUND_TRUTH
from ui_components import (
    get_custom_css,
    render_hero_banner,
    render_pipeline_stepper,
    render_kpi_card_html,
    get_settlement_donut_chart,
    get_confidence_breakdown_chart,
    get_financial_breakdown_bar_chart
)
from database import (
    init_db,
    insert_invoices,
    insert_payments,
    log_invalid_records,
    get_existing_ids,
    fetch_table_data,
    get_database_stats,
    reset_database,
    save_matches,
    update_match_status,
    record_allocation,
    get_allocations,
    get_rejected_pairs,
    delete_allocation,
    DEFAULT_DB_PATH
)
from sample_data import INVOICE_SAMPLE_CSV, PAYMENT_SAMPLE_CSV

# Page configuration
st.set_page_config(
    page_title="Financial Reconciliation SaaS | Modules 1 - 4",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply Ultra-Modern FinTech SaaS Stylesheet
st.markdown(get_custom_css(), unsafe_allow_html=True)

# Initialize database
init_db()

# Sidebar Navigation
st.sidebar.markdown("""
<div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
    <div style="background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%); width: 44px; height: 44px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 22px; box-shadow: 0 4px 10px rgba(79, 70, 229, 0.35);">
        ⚖️
    </div>
    <div>
        <div style="font-size: 1.12rem; font-weight: 800; color: #0F172A; letter-spacing: -0.01em;">ReconcileAI</div>
        <div style="font-size: 0.74rem; font-weight: 600; color: #6366F1; text-transform: uppercase; letter-spacing: 0.05em;">Enterprise SaaS</div>
    </div>
</div>
""", unsafe_allow_html=True)

menu_choice = st.sidebar.radio(
    "Navigation Menu",
    [
        "📤 Module 1: Data Import & Validation",
        "🤖 Module 2: Intelligent Matching",
        "⚖️ Module 3: Match Review & Reconciliation",
        "📈 Module 4: Dashboard, Reporting & Evaluation",
        "🗄️ SQLite Database Explorer",
        "🧪 Download Sample CSVs",
        "📋 Rules & Architecture Reference"
    ]
)

# 1-Click Fast Pipeline Demo in Sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("#### ⚡ 1-Click Complete Pipeline")
if st.sidebar.button("🚀 Run Full Demo Experience", type="primary", use_container_width=True):
    with st.spinner("Executing full end-to-end reconciliation pipeline..."):
        # 1. Clean sample invoices and payments
        inv_raw = pd.read_csv(io.StringIO(INVOICE_SAMPLE_CSV))
        pmt_raw = pd.read_csv(io.StringIO(PAYMENT_SAMPLE_CSV))
        res_inv = validate_records(inv_raw, record_type="invoice")
        res_pmt = validate_records(pmt_raw, record_type="payment")
        
        clean_inv = res_inv["valid_df"]
        clean_pmt = res_pmt["valid_df"]

        st.session_state["clean_invoices_df"] = clean_inv
        st.session_state["clean_payments_df"] = clean_pmt
        st.session_state["m3_invoices_df"] = clean_inv
        st.session_state["m3_payments_df"] = clean_pmt

        # 2. Persist to DB
        b_id = f"DEMO-{datetime.now(timezone.utc).strftime('%H%M%S')}"
        insert_invoices(clean_inv, batch_id=b_id)
        insert_payments(clean_pmt, batch_id=b_id)

        # 3. Match
        matcher = IntelligentTransactionMatcher()
        match_out = matcher.match_transactions(clean_inv, clean_pmt)
        st.session_state["match_results"] = match_out
        save_matches(match_out["matches_df"])

        # 4. Auto confirm high confidence
        high_m = match_out["matches_df"][match_out["matches_df"]["confidence"] == "High"]
        for _, h in high_m.iterrows():
            record_allocation(
                invoice_id=str(h["invoice_id"]),
                payment_id=str(h["payment_id"]),
                allocated_amount=float(h["payment_amount"]),
                status="CONFIRMED",
                user_notes="1-Click Demo confirmed match"
            )

        st.toast("🎉 Full pipeline executed with high confidence allocations confirmed!", icon="🚀")
        st.rerun()

# Sidebar Live Database Stats
st.sidebar.markdown("---")
st.sidebar.subheader("🗄️ Database Health")
try:
    db_stats = get_database_stats()
    col_sb1, col_sb2 = st.sidebar.columns(2)
    with col_sb1:
        st.metric("Invoices", db_stats["total_invoices"])
        st.metric("Payments", db_stats["total_payments"])
    with col_sb2:
        st.metric("Confirmed Alloc", db_stats.get("confirmed_allocations_count", 0))
        st.metric("Rejected Log", db_stats.get("rejected_allocations_count", 0))
except Exception as e:
    st.sidebar.error(f"DB Error: {e}")

st.sidebar.caption("🔒 SQLite Persistence Active | Decimal Precision Engine")


# ==============================================================================
# VIEW 1: MODULE 1 - DATA IMPORT & VALIDATION
# ==============================================================================
if menu_choice == "📤 Module 1: Data Import & Validation":
    render_hero_banner(
        title="Module 1: Data Import & Validation Engine",
        subtitle="Ingest heterogeneous financial CSV records, sanitize customer identities, normalize dates to ISO standards, flag invalid amounts, and store clean records into SQLite.",
        badge_text="Pipeline Stage 01 • Data Ingestion"
    )
    render_pipeline_stepper(current_step=1)

    record_type = st.radio(
        "Select Document Type to Ingest & Validate:",
        ["invoice", "payment"],
        format_func=lambda x: "📄 Invoices File (invoice_id, customer_name, amount, transaction_date)" if x == "invoice" else "💳 Payments File (payment_id, customer_name, amount, transaction_date, ref invoice_id)",
        horizontal=True
    )

    col_upload, col_sample_btn = st.columns([3, 1])
    with col_upload:
        uploaded_file = st.file_uploader(
            f"Upload {record_type.capitalize()} CSV File",
            type=["csv"],
            help="Upload CSV with headers matching standard columns or aliases."
        )

    with col_sample_btn:
        st.write("Or use pre-built test dataset:")
        load_sample = st.button(f"⚡ Load Sample {record_type.capitalize()} CSV", use_container_width=True)

    df_raw = None
    file_source_name = ""

    if uploaded_file is not None:
        try:
            df_raw = pd.read_csv(uploaded_file)
            file_source_name = uploaded_file.name
            st.success(f"Uploaded file `{file_source_name}` loaded successfully! ({len(df_raw)} records found)")
        except Exception as err:
            st.error(f"Error reading uploaded CSV file: {err}")
    elif load_sample:
        sample_str = INVOICE_SAMPLE_CSV if record_type == "invoice" else PAYMENT_SAMPLE_CSV
        df_raw = pd.read_csv(io.StringIO(sample_str))
        file_source_name = f"sample_{record_type}s.csv"
        st.session_state["cached_df_raw"] = df_raw
        st.session_state["cached_file_name"] = file_source_name
        st.info(f"Loaded built-in test dataset: `{file_source_name}` ({len(df_raw)} rows with intentional valid, messy, and invalid records).")
    elif "cached_df_raw" in st.session_state:
        df_raw = st.session_state["cached_df_raw"]
        file_source_name = st.session_state.get("cached_file_name", "sample.csv")

    if df_raw is not None and not df_raw.empty:
        # Step 1: Raw Preview & Mapping
        with st.expander("🔍 Step 1: Raw CSV Preview & Column Detection", expanded=False):
            st.dataframe(df_raw.head(10), use_container_width=True)
            aliases = INVOICE_COLUMN_ALIASES if record_type == "invoice" else PAYMENT_COLUMN_ALIASES
            detected_map = map_columns(df_raw, aliases)
            st.caption(f"**Auto-Detected Column Mapping:** `{detected_map}`")

        # Step 2: Validate Action
        st.markdown("### ⚙️ Step 2: Validation & Normalization Engine")
        col_btn1, _ = st.columns([2, 4])
        with col_btn1:
            run_validation = st.button("🚀 Validate & Normalize Records", type="primary", use_container_width=True)

        if run_validation or f"{record_type}_validation_result" in st.session_state:
            if run_validation:
                with st.spinner("Validating fields, checking duplicates, and normalizing data..."):
                    id_col_key = "invoice_id" if record_type == "invoice" else "payment_id"
                    existing_db_ids = get_existing_ids(
                        table_name="invoices" if record_type == "invoice" else "payments",
                        id_column=id_col_key
                    )
                    val_result = validate_records(
                        df=df_raw,
                        record_type=record_type,
                        existing_db_ids=existing_db_ids
                    )
                    st.session_state[f"{record_type}_validation_result"] = val_result
                    st.session_state[f"clean_{record_type}s_df"] = val_result["valid_df"]
            else:
                val_result = st.session_state[f"{record_type}_validation_result"]

            valid_df = val_result["valid_df"]
            invalid_df = val_result["invalid_df"]
            metrics = val_result["metrics"]

            # Visual KPI Cards
            st.markdown("#### 📊 Processing Results Summary")
            kpi_c1, kpi_c2, kpi_c3, kpi_c4, kpi_c5 = st.columns(5)
            
            with kpi_c1:
                st.markdown(render_kpi_card_html("Total Ingested", str(metrics["total_rows"]), "Rows processed in CSV", "📑", "indigo"), unsafe_allow_html=True)
            with kpi_c2:
                st.markdown(render_kpi_card_html("Clean & Valid", str(metrics["valid_count"]), "100% verified records", "✅", "emerald", "#ECFDF5"), unsafe_allow_html=True)
            with kpi_c3:
                st.markdown(render_kpi_card_html("Errors Flagged", str(metrics["invalid_count"]), "Rejected for correction", "❌", "rose", "#FEF2F2"), unsafe_allow_html=True)
            with kpi_c4:
                dup_tot = metrics["file_duplicate_count"] + metrics["db_duplicate_count"]
                st.markdown(render_kpi_card_html("Duplicates", str(dup_tot), "File & DB duplicate IDs", "⚠️", "amber", "#FFFBEB"), unsafe_allow_html=True)
            with kpi_c5:
                st.markdown(render_kpi_card_html("Valid Amount", f"${metrics['total_valid_amount']:,.2f}", "Eligible financial value", "💰", "sky", "#F0F9FF"), unsafe_allow_html=True)

            st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

            tab_valid, tab_invalid, tab_duplicates, tab_comparison = st.tabs([
                f"✅ Clean Valid Records ({len(valid_df)})",
                f"❌ Invalid Records Requiring Correction ({len(invalid_df)})",
                f"⚠️ Duplicate Details ({metrics['file_duplicate_count'] + metrics['db_duplicate_count']})",
                "🔄 Normalization Comparison"
            ])

            # TAB 1: Clean Valid Records
            with tab_valid:
                if not valid_df.empty:
                    st.success(f"{len(valid_df)} record(s) successfully normalized and passed all validation checks!")
                    st.dataframe(valid_df, use_container_width=True)

                    col_save, col_dl, col_goto_m2 = st.columns([2, 2, 2])
                    batch_id = f"BATCH-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

                    with col_save:
                        if st.button("💾 Store Valid Records in SQLite Database", type="primary", use_container_width=True):
                            with st.spinner("Persisting records into SQLite..."):
                                if record_type == "invoice":
                                    inserted, skipped = insert_invoices(valid_df, batch_id=batch_id)
                                else:
                                    inserted, skipped = insert_payments(valid_df, batch_id=batch_id)

                                st.toast(f"Saved {inserted} records into `{record_type}s` table! (Skipped {skipped} duplicates).", icon="💾")
                                st.rerun()

                    with col_dl:
                        csv_data = valid_df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            label="📥 Download Valid CSV",
                            data=csv_data,
                            file_name=f"validated_{record_type}s_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

                    with col_goto_m2:
                        st.info("👉 Ready to match? Move to **Module 2: Intelligent Matching**!")
                else:
                    st.warning("No records passed validation. Review the 'Invalid Records' tab to inspect and fix errors.")

            # TAB 2: Invalid Records & Errors
            with tab_invalid:
                if not invalid_df.empty:
                    st.error(f"{len(invalid_df)} record(s) failed validation and require correction.")

                    display_cols = ["row_number", "record_id", "problematic_field", "error_type", "error_details"]
                    st.dataframe(
                        invalid_df[display_cols],
                        column_config={
                            "row_number": st.column_config.NumberColumn("CSV Row #", width="small"),
                            "record_id": st.column_config.TextColumn("Record ID", width="medium"),
                            "problematic_field": st.column_config.TextColumn("Failed Field", width="medium"),
                            "error_type": st.column_config.TextColumn("Error Category", width="medium"),
                            "error_details": st.column_config.TextColumn("Reason & Suggestion", width="large")
                        },
                        use_container_width=True
                    )

                    col_dl_err, col_log_err = st.columns([2, 2])
                    with col_dl_err:
                        err_csv = invalid_df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            label="📥 Download Rejected Records for Correction (CSV)",
                            data=err_csv,
                            file_name=f"rejected_{record_type}s_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

                    with col_log_err:
                        if st.button("📝 Log Rejections into SQLite Audit Log", use_container_width=True):
                            batch_id = f"ERR-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
                            logged = log_invalid_records(invalid_df.to_dict(orient="records"), record_type=record_type, batch_id=batch_id)
                            st.toast(f"Logged {logged} rejected records to `invalid_records` audit table.", icon="📝")
                else:
                    st.success("🎉 No invalid records found! All records passed validation.")

            # TAB 3: Duplicates Breakdown
            with tab_duplicates:
                st.markdown("#### ⚠️ Duplicate Records Identification")
                dup_mask = invalid_df["error_type"].str.contains("DUPLICATE", na=False) if not invalid_df.empty else pd.Series(dtype=bool)
                dup_df = invalid_df[dup_mask] if not invalid_df.empty else pd.DataFrame()

                col_fdup, col_dbdup = st.columns(2)
                with col_fdup:
                    st.metric("Duplicates in this CSV File", metrics["file_duplicate_count"])
                with col_dbdup:
                    st.metric("Duplicates Already in Database", metrics["db_duplicate_count"])

                if not dup_df.empty:
                    st.write("Identified Duplicate Records:")
                    st.dataframe(dup_df[["row_number", "record_id", "error_type", "error_details"]], use_container_width=True)
                else:
                    st.info("No duplicate IDs identified in this batch.")

            # TAB 4: Normalization Comparison
            with tab_comparison:
                st.markdown("#### 🔄 Data Normalization Breakdown")
                st.markdown("""
                The validation engine performs automated normalization:
                - **Customer Name**: Whitespace stripped, internal spaces condensed, trailing punctuation removed, title-cased.
                - **Transaction Date**: Converted to standardized ISO `YYYY-MM-DD`.
                - **Amount**: Cleaned of currency symbols (`$`, `€`, `₹`) & commas, rounded to 2 decimal places.
                - **Description**: Capitalized, sanitized default text.
                """)
                if not valid_df.empty:
                    st.write("Cleaned & Normalized Output Sample:")
                    st.dataframe(valid_df.head(5), use_container_width=True)


# ==============================================================================
# VIEW 2: MODULE 2 - INTELLIGENT TRANSACTION MATCHING
# ==============================================================================
elif menu_choice == "🤖 Module 2: Intelligent Matching":
    render_hero_banner(
        title="Module 2: Intelligent RapidFuzz Matching Engine",
        subtitle="Leverage RapidFuzz token sorting, invoice reference extraction, date window analysis, and amount discrepancy checks to automatically suggest payment-to-invoice correlations.",
        badge_text="Pipeline Stage 02 • AI Matching"
    )
    render_pipeline_stepper(current_step=2)

    # Data Source Selection
    st.markdown("### 📥 Step 1: Select Records to Match")
    data_source_mode = st.radio(
        "Choose Match Data Source:",
        [
            "🗄️ From SQLite Database (Saved Records)",
            "⚡ Built-in Demo Test Set (INV-101/102/103 & PAY-201/202/203)",
            "📤 From Module 1 Validated Session"
        ],
        horizontal=True
    )

    df_invoices_to_match = None
    df_payments_to_match = None

    if "From SQLite Database" in data_source_mode:
        inv_data = fetch_table_data("invoices")
        pmt_data = fetch_table_data("payments")

        if inv_data and pmt_data:
            df_invoices_to_match = pd.DataFrame(inv_data)
            df_payments_to_match = pd.DataFrame(pmt_data)
            st.success(f"Loaded {len(df_invoices_to_match)} invoices and {len(df_payments_to_match)} payments from SQLite database.")
        else:
            st.warning(f"Database currently holds {len(inv_data)} invoices and {len(pmt_data)} payments. Please import records first or choose 'Built-in Demo Test Set'.")

    elif "Built-in Demo Test Set" in data_source_mode:
        inv_raw = pd.read_csv(io.StringIO(INVOICE_SAMPLE_CSV))
        pmt_raw = pd.read_csv(io.StringIO(PAYMENT_SAMPLE_CSV))
        res_inv = validate_records(inv_raw, record_type="invoice")
        res_pmt = validate_records(pmt_raw, record_type="payment")
        df_invoices_to_match = res_inv["valid_df"]
        df_payments_to_match = res_pmt["valid_df"]
        st.info(f"Loaded {len(df_invoices_to_match)} clean invoices and {len(df_payments_to_match)} clean payments from Demo Data (includes prompt examples INV-101, 102, 103).")

    elif "From Module 1 Validated Session" in data_source_mode:
        df_invoices_to_match = st.session_state.get("clean_invoices_df")
        df_payments_to_match = st.session_state.get("clean_payments_df")

        if df_invoices_to_match is None or df_payments_to_match is None:
            st.warning("Please validate both an Invoice file and a Payment file in **Module 1** first to use session data.")
        else:
            st.success(f"Using {len(df_invoices_to_match)} invoices and {len(df_payments_to_match)} payments from current session.")

    # Matching Configuration Expander
    with st.expander("⚙️ Advanced Matching Configuration & RapidFuzz Weights", expanded=False):
        c_conf1, c_conf2, c_conf3 = st.columns(3)
        with c_conf1:
            name_threshold = st.slider("Customer Name Similarity Threshold (%)", min_value=50.0, max_value=95.0, value=70.0, step=5.0)
        with c_conf2:
            max_date_gap = st.slider("Max Plausible Settlement Gap (Days)", min_value=15, max_value=180, value=90, step=15)
        with c_conf3:
            amt_tolerance = st.slider("Amount Rounding Tolerance (%)", min_value=0.0, max_value=5.0, value=0.0, step=0.5)

    col_run_match, _ = st.columns([2, 4])
    with col_run_match:
        run_match = st.button("🚀 Run Intelligent Matching Engine", type="primary", use_container_width=True)

    if (df_invoices_to_match is not None and df_payments_to_match is not None and not df_invoices_to_match.empty and not df_payments_to_match.empty):
        if run_match or "match_results" in st.session_state:
            if run_match:
                with st.spinner("Analyzing references, checking user rejections, and running RapidFuzz algorithms..."):
                    matcher = IntelligentTransactionMatcher(
                        customer_name_threshold=name_threshold,
                        amount_tolerance_percent=amt_tolerance,
                        max_date_gap_days=max_date_gap
                    )
                    user_rejected_pairs = get_rejected_pairs()

                    match_res = matcher.match_transactions(
                        invoices_df=df_invoices_to_match,
                        payments_df=df_payments_to_match,
                        rejected_pairs=user_rejected_pairs
                    )
                    st.session_state["match_results"] = match_res
                    st.session_state["m3_invoices_df"] = df_invoices_to_match
                    st.session_state["m3_payments_df"] = df_payments_to_match
                    st.toast("Matching engine finished processing!", icon="✨")
            else:
                match_res = st.session_state["match_results"]

            matches_df = match_res["matches_df"]
            unmatched_invoices_df = match_res["unmatched_invoices_df"]
            unmatched_payments_df = match_res["unmatched_payments_df"]
            summary = match_res["summary_metrics"]

            # Visual KPI Cards
            st.markdown("### 📊 Matching Results & Confidence Overview")
            mk1, mk2, mk3, mk4, mk5, mk6 = st.columns(6)
            with mk1:
                st.markdown(render_kpi_card_html("Total Matches", str(summary["total_matches"]), "Correlations proposed", "🎯", "indigo"), unsafe_allow_html=True)
            with mk2:
                st.markdown(render_kpi_card_html("High Confidence", str(summary["high_confidence_count"]), "Exact match verified", "🟢", "emerald", "#ECFDF5"), unsafe_allow_html=True)
            with mk3:
                st.markdown(render_kpi_card_html("Medium Conf", str(summary["medium_confidence_count"]), "Fuzzy name / clean amt", "🟡", "sky", "#F0F9FF"), unsafe_allow_html=True)
            with mk4:
                st.markdown(render_kpi_card_html("Review Required", str(summary["review_required_count"]), "Discrepancy / ambiguity", "🔴", "rose", "#FEF2F2"), unsafe_allow_html=True)
            with mk5:
                st.markdown(render_kpi_card_html("Unmatched Pymts", str(summary["unmatched_payments_count"]), "Orphan deposits", "❓", "amber", "#FFFBEB"), unsafe_allow_html=True)
            with mk6:
                st.markdown(render_kpi_card_html("Unmatched Invs", str(summary["unmatched_invoices_count"]), "Unpaid receivables", "📄", "indigo"), unsafe_allow_html=True)

            st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

            # Interactive Chart + Match Highlights Box
            ch_col1, ch_col2 = st.columns([1, 2])
            with ch_col1:
                st.markdown("<div class='chart-box'><div class='chart-title'>📊 Confidence Distribution</div>", unsafe_allow_html=True)
                conf_donut = get_confidence_breakdown_chart(matches_df)
                if conf_donut:
                    st.altair_chart(conf_donut, use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with ch_col2:
                st.markdown("<div class='chart-box'><div class='chart-title'>💡 Matching Engine Intelligence Matrix</div>", unsafe_allow_html=True)
                st.markdown("""
                - **Exact Reference & Amount (High Confidence)**: Evaluated with primary priority; awarded full 40 pts for ID and 20 pts for amount.
                - **Fuzzy Name Resolution (RapidFuzz)**: Corporate suffixes (`LLC`, `Corp`, `Inc`) stripped, token sort ratio applied for reordered words.
                - **Amount Discrepancy Flagging**: Automatically flags partial settlements and overpayments for human review.
                - **Settlement Velocity Window**: Detects prompt settlements (0–14 days) and flags date anomalies if payment predates invoice.
                """)
                st.markdown("</div>", unsafe_allow_html=True)

            tab_matches, tab_deep_dive, tab_review, tab_unmatched = st.tabs([
                f"📋 Suggested Matches ({len(matches_df)})",
                "🔍 Match Deep-Dive & Inspection",
                f"⚠️ Flagged for Review ({summary['review_required_count']})",
                f"❓ Unmatched Records ({summary['unmatched_payments_count'] + summary['unmatched_invoices_count']})"
            ])

            # TAB 1: ALL SUGGESTED MATCHES
            with tab_matches:
                st.markdown("#### Suggested Invoice-to-Payment Pairs")

                conf_filter = st.selectbox(
                    "Filter by Confidence Level:",
                    ["All", "High", "Medium", "Review required"]
                )

                filtered_matches = matches_df if conf_filter == "All" else matches_df[matches_df["confidence"] == conf_filter]

                if not filtered_matches.empty:
                    display_df = filtered_matches[[
                        "invoice_id", "invoice_amount", "payment_id", "payment_amount",
                        "amount_diff", "confidence", "matching_evidence", "review_flags"
                    ]].copy()

                    st.dataframe(
                        display_df,
                        column_config={
                            "invoice_id": st.column_config.TextColumn("Invoice", width="small"),
                            "invoice_amount": st.column_config.NumberColumn("Inv Amount ($)", format="$%.2f", width="small"),
                            "payment_id": st.column_config.TextColumn("Payment", width="small"),
                            "payment_amount": st.column_config.NumberColumn("Paid Amount ($)", format="$%.2f", width="small"),
                            "amount_diff": st.column_config.NumberColumn("Diff ($)", format="$%.2f", width="small"),
                            "confidence": st.column_config.TextColumn("Confidence", width="small"),
                            "matching_evidence": st.column_config.TextColumn("Matching Evidence & Explanation", width="large"),
                            "review_flags": st.column_config.TextColumn("Flags", width="medium")
                        },
                        use_container_width=True
                    )

                    col_save_m, col_dl_m, col_goto_m3 = st.columns([2, 2, 2])
                    with col_save_m:
                        if st.button("💾 Store Matches in SQLite Database", type="primary", use_container_width=True):
                            saved_cnt = save_matches(matches_df)
                            st.toast(f"Saved {saved_cnt} match records to SQLite `matches` table!", icon="💾")
                            st.rerun()

                    with col_dl_m:
                        csv_matches = matches_df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "📥 Download Suggested Matches (CSV)",
                            data=csv_matches,
                            file_name=f"transaction_matches_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )

                    with col_goto_m3:
                        st.info("👉 Ready to review & reconcile? Head over to **Module 3: Match Review & Reconciliation**!")
                else:
                    st.info("No matches match the selected filter.")

            # TAB 2: DEEP DIVE & INSPECTION
            with tab_deep_dive:
                st.markdown("#### 🔍 Side-by-Side Match Inspection")
                if not matches_df.empty:
                    match_options = [f"{row['payment_id']} ⟷ {row['invoice_id']} ({row['confidence']})" for _, row in matches_df.iterrows()]
                    selected_match_label = st.selectbox("Select Match to Inspect:", match_options)
                    selected_idx = match_options.index(selected_match_label)
                    match_item = matches_df.iloc[selected_idx]

                    col_inv_card, col_pmt_card = st.columns(2)
                    with col_inv_card:
                        st.markdown(f"""
                        <div class="kpi-card accent-indigo">
                            <div class="kpi-header">
                                <span class="kpi-title">📄 Invoice Record</span>
                                <span class="pill-badge pill-high">{match_item['invoice_id']}</span>
                            </div>
                            <div style="margin: 8px 0; font-size: 1.1rem; font-weight: 700; color: #0F172A;">{match_item['invoice_customer']}</div>
                            <div style="font-size: 1.6rem; font-weight: 800; color: #4F46E5;">${match_item['invoice_amount']:,.2f}</div>
                            <div style="font-size: 0.82rem; color: #64748B; margin-top: 6px;">Issue Date: <b>{match_item['invoice_date']}</b></div>
                        </div>
                        """, unsafe_allow_html=True)

                    with col_pmt_card:
                        st.markdown(f"""
                        <div class="kpi-card accent-emerald">
                            <div class="kpi-header">
                                <span class="kpi-title">💳 Payment Record</span>
                                <span class="pill-badge pill-high">{match_item['payment_id']}</span>
                            </div>
                            <div style="margin: 8px 0; font-size: 1.1rem; font-weight: 700; color: #0F172A;">{match_item['payment_customer']}</div>
                            <div style="font-size: 1.6rem; font-weight: 800; color: #10B981;">${match_item['payment_amount']:,.2f}</div>
                            <div style="font-size: 0.82rem; color: #64748B; margin-top: 6px;">Payment Date: <b>{match_item['payment_date']}</b></div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("##### 💡 Evidence & Scoring Breakdown")
                    st.info(f"**Matching Evidence:** {match_item['matching_evidence']}")
                    
                    e1, e2, e3 = st.columns(3)
                    e1.metric("RapidFuzz Name Similarity", f"{match_item['customer_similarity']:.0f}%")
                    e2.metric("Date Difference", f"{match_item['date_gap_days']} Days")
                    e3.metric("Amount Discrepancy", f"${match_item['amount_diff']:+,.2f}")
                    
                    st.caption(f"**Assigned Review Flags:** `{match_item['review_flags']}`")

            # TAB 3: FLAGGED FOR REVIEW
            with tab_review:
                st.markdown("#### ⚠️ Ambiguous Cases & Discrepancies Requiring Manual Review")
                review_cases = matches_df[matches_df["confidence"] == "Review required"]

                if not review_cases.empty:
                    st.warning(f"{len(review_cases)} case(s) flagged for human review due to amount mismatches, date anomalies, or ambiguous candidates.")
                    st.dataframe(
                        review_cases[["invoice_id", "payment_id", "invoice_amount", "payment_amount", "amount_diff", "matching_evidence", "review_flags"]],
                        use_container_width=True
                    )
                else:
                    st.success("🎉 No ambiguous cases or amount mismatches! All matches have High or Medium confidence.")

            # TAB 4: UNMATCHED RECORDS
            with tab_unmatched:
                st.markdown("#### ❓ Unpaired Records")
                col_un_p, col_un_i = st.columns(2)
                with col_un_p:
                    st.subheader(f"Unmatched Payments ({len(unmatched_payments_df)})")
                    if not unmatched_payments_df.empty:
                        st.dataframe(unmatched_payments_df[["payment_id", "customer_name", "amount", "transaction_date"]], use_container_width=True)
                    else:
                        st.info("All payments found a match candidate.")

                with col_un_i:
                    st.subheader(f"Unmatched Invoices ({len(unmatched_invoices_df)})")
                    if not unmatched_invoices_df.empty:
                        st.dataframe(unmatched_invoices_df[["invoice_id", "customer_name", "amount", "transaction_date"]], use_container_width=True)
                    else:
                        st.info("All invoices found a match candidate.")


# ==============================================================================
# VIEW 3: MODULE 3 - MATCH REVIEW AND RECONCILIATION
# ==============================================================================
elif menu_choice == "⚖️ Module 3: Match Review & Reconciliation":
    render_hero_banner(
        title="Module 3: Match Review & Reconciliation Ledger",
        subtitle="Verify match suggestions, confirm allocations safely with anti-double-spending guards, preserve user corrections, and compute live outstanding balances with exact Decimal arithmetic.",
        badge_text="Pipeline Stage 03 • Reconciliation"
    )
    render_pipeline_stepper(current_step=3)

    # 1. Load active data for reconciliation
    invoices_for_rec = st.session_state.get("m3_invoices_df")
    payments_for_rec = st.session_state.get("m3_payments_df")

    if invoices_for_rec is None or invoices_for_rec.empty:
        db_invs = fetch_table_data("invoices")
        if db_invs:
            invoices_for_rec = pd.DataFrame(db_invs)
        else:
            inv_raw = pd.read_csv(io.StringIO(INVOICE_SAMPLE_CSV))
            invoices_for_rec = validate_records(inv_raw, record_type="invoice")["valid_df"]

    if payments_for_rec is None or payments_for_rec.empty:
        db_pmts = fetch_table_data("payments")
        if db_pmts:
            payments_for_rec = pd.DataFrame(db_pmts)
        else:
            pmt_raw = pd.read_csv(io.StringIO(PAYMENT_SAMPLE_CSV))
            payments_for_rec = validate_records(pmt_raw, record_type="payment")["valid_df"]

    allocations_list = get_allocations()
    allocations_df = pd.DataFrame(allocations_list) if allocations_list else pd.DataFrame(
        columns=["allocation_id", "invoice_id", "payment_id", "allocated_amount", "status", "user_notes", "created_at"]
    )

    matches_data = fetch_table_data("matches")
    if matches_data:
        suggested_matches_df = pd.DataFrame(matches_data)
    elif "match_results" in st.session_state and not st.session_state["match_results"]["matches_df"].empty:
        suggested_matches_df = st.session_state["match_results"]["matches_df"]
    else:
        matcher = IntelligentTransactionMatcher()
        rejected_pairs_set = get_rejected_pairs()
        m_res = matcher.match_transactions(invoices_for_rec, payments_for_rec, rejected_pairs=rejected_pairs_set)
        suggested_matches_df = m_res["matches_df"]

    # Calculate balances using Decimal
    invoice_balances_df = ReconciliationEngine.calculate_invoice_balances(invoices_for_rec, allocations_df)
    payment_allocations_df = ReconciliationEngine.calculate_payment_allocations(payments_for_rec, allocations_df)
    unresolved_dict = ReconciliationEngine.get_unresolved_transactions(invoice_balances_df, payment_allocations_df)

    tot_invoiced = float(sum(to_decimal(r.get("amount", 0.0)) for _, r in invoices_for_rec.iterrows()))
    tot_confirmed_paid = float(sum(to_decimal(r.get("allocated_amount", 0.0)) for _, r in allocations_df[allocations_df["status"] == "CONFIRMED"].iterrows())) if not allocations_df.empty else 0.0
    tot_outstanding = tot_invoiced - tot_confirmed_paid

    st.markdown("### 📊 Financial Reconciliation Summary")
    r_kpi1, r_kpi2, r_kpi3, r_kpi4, r_kpi5, r_kpi6 = st.columns(6)
    with r_kpi1:
        st.markdown(render_kpi_card_html("Total Invoiced", f"${tot_invoiced:,.2f}", "Gross receivable", "📄", "indigo"), unsafe_allow_html=True)
    with r_kpi2:
        st.markdown(render_kpi_card_html("Confirmed Paid", f"${tot_confirmed_paid:,.2f}", "Settled funds collected", "✅", "emerald", "#ECFDF5"), unsafe_allow_html=True)
    with r_kpi3:
        st.markdown(render_kpi_card_html("Outstanding", f"${tot_outstanding:,.2f}", "Remaining receivable", "⏳", "rose", "#FEF2F2"), unsafe_allow_html=True)
    with r_kpi4:
        st.markdown(render_kpi_card_html("Paid Invoices", str((invoice_balances_df["status"] == "PAID").sum()), "100% Settled", "🏆", "emerald", "#ECFDF5"), unsafe_allow_html=True)
    with r_kpi5:
        st.markdown(render_kpi_card_html("Partially Paid", str((invoice_balances_df["status"] == "PARTIALLY PAID").sum()), "Partial deposits", "🟡", "amber", "#FFFBEB"), unsafe_allow_html=True)
    with r_kpi6:
        st.markdown(render_kpi_card_html("Unpaid Invoices", str((invoice_balances_df["status"] == "UNPAID").sum()), "Awaiting settlement", "🔴", "rose", "#FEF2F2"), unsafe_allow_html=True)

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

    # Side-by-side Visual Charts
    c_m3_1, c_m3_2 = st.columns([1, 1])
    with c_m3_1:
        st.markdown("<div class='chart-box'><div class='chart-title'>📊 Invoice Settlement Status Distribution</div>", unsafe_allow_html=True)
        ch_donut = get_settlement_donut_chart(invoice_balances_df)
        if ch_donut:
            st.altair_chart(ch_donut, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with c_m3_2:
        st.markdown("<div class='chart-box'><div class='chart-title'>💰 Gross Receivable vs Confirmed Collections</div>", unsafe_allow_html=True)
        ch_bar = get_financial_breakdown_bar_chart(tot_invoiced, tot_confirmed_paid, tot_outstanding)
        st.altair_chart(ch_bar, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    tab_review_matches, tab_manual_match, tab_balances, tab_unresolved = st.tabs([
        "🧐 1. Review Suggested Matches",
        "✍️ 2. Manual Match & Custom Allocation",
        "📊 3. Outstanding Balances & Ledger",
        "❓ 4. Unresolved Transactions & Audit"
    ])

    # TAB 1: REVIEW SUGGESTED MATCHES
    with tab_review_matches:
        st.markdown("#### 🧐 Review & Act on Suggested Transaction Matches")
        st.markdown("""
        Review suggestions below. When you **Confirm** a match, funds are officially allocated and invoice balances updated.
        When you **Reject** a match, your decision is permanently stored in SQLite, **preventing it from ever being silently reintroduced**.
        """)

        col_batch1, _ = st.columns([2, 4])
        with col_batch1:
            if not suggested_matches_df.empty:
                high_conf_matches = suggested_matches_df[suggested_matches_df["confidence"] == "High"]
                if not high_conf_matches.empty:
                    if st.button(f"⚡ Batch Confirm All High-Confidence Matches ({len(high_conf_matches)})", type="primary"):
                        confirmed_count = 0
                        for _, h_row in high_conf_matches.iterrows():
                            i_id = str(h_row["invoice_id"]).strip().upper()
                            p_id = str(h_row["payment_id"]).strip().upper()
                            alloc_amt = to_decimal(h_row["payment_amount"])
                            
                            is_valid, _ = ReconciliationEngine.validate_allocation(
                                payment_id=p_id,
                                invoice_id=i_id,
                                amount_to_allocate=alloc_amt,
                                payments_df=payments_for_rec,
                                invoices_df=invoices_for_rec,
                                confirmed_allocations_df=allocations_df
                            )
                            if is_valid:
                                record_allocation(
                                    invoice_id=i_id,
                                    payment_id=p_id,
                                    allocated_amount=float(alloc_amt),
                                    status="CONFIRMED",
                                    user_notes="Batch confirmed high-confidence match"
                                )
                                confirmed_count += 1
                        st.balloons()
                        st.toast(f"Successfully confirmed {confirmed_count} high-confidence matches!", icon="🎉")
                        st.rerun()

        if not suggested_matches_df.empty:
            active_alloc_pairs = {
                (str(r["invoice_id"]).strip().upper(), str(r["payment_id"]).strip().upper()): str(r["status"]).upper()
                for _, r in allocations_df.iterrows()
            } if not allocations_df.empty else {}

            for idx, m_row in suggested_matches_df.iterrows():
                inv_id = str(m_row["invoice_id"]).strip().upper()
                pmt_id = str(m_row["payment_id"]).strip().upper()
                inv_amt = float(m_row.get("invoice_amount", 0.0))
                pmt_amt = float(m_row.get("payment_amount", 0.0))
                diff = pmt_amt - inv_amt
                conf = str(m_row.get("confidence", "Review required"))
                evidence = str(m_row.get("matching_evidence", ""))
                flags = str(m_row.get("review_flags", ""))

                existing_decision = active_alloc_pairs.get((inv_id, pmt_id))

                with st.expander(
                    f"Pair #{idx+1}: {pmt_id} (${pmt_amt:,.2f}) ⟷ {inv_id} (${inv_amt:,.2f}) | [{conf}] {f'— Decision: {existing_decision}' if existing_decision else ''}",
                    expanded=(existing_decision is None and conf == "Review required")
                ):
                    card_c1, card_c2, card_c3 = st.columns([2, 2, 3])
                    with card_c1:
                        st.write(f"**Invoice ID:** `{inv_id}`")
                        st.write(f"**Invoice Amount:** `${inv_amt:,.2f}`")
                    with card_c2:
                        st.write(f"**Payment ID:** `{pmt_id}`")
                        st.write(f"**Payment Amount:** `${pmt_amt:,.2f}`")
                    with card_c3:
                        st.write(f"**Amount Difference:** `${diff:+,.2f}`")
                        st.write(f"**Confidence Level:** `{conf}`")

                    st.info(f"**Matching Evidence:** {evidence}")

                    if abs(diff) > 0.001:
                        st.warning(f"⚠️ **Amount Discrepancy Detected:** Payment amount differs by `${diff:+,.2f}`. Confirming this will result in a partial allocation or overpayment.")
                    if "AMBIGUOUS" in flags:
                        st.error("⚠️ **Ambiguous Candidate:** Multiple invoices share similar attributes. Verify before confirming.")

                    if existing_decision == "CONFIRMED":
                        st.success("✅ This match is already **CONFIRMED** in SQLite.")
                    elif existing_decision == "REJECTED":
                        st.error("❌ This match was **REJECTED** by user. It will not be suggested as an active match.")
                    else:
                        st.markdown("##### Take Action:")
                        act_c1, act_c2, act_c3 = st.columns([2, 3, 2])
                        with act_c1:
                            default_alloc = min(inv_amt, pmt_amt) if pmt_amt > 0 else inv_amt
                            alloc_val = st.number_input(
                                f"Allocation Amount ($) for {pmt_id}:",
                                min_value=0.01,
                                max_value=float(pmt_amt) if pmt_amt > 0 else 100000.0,
                                value=float(default_alloc),
                                step=10.0,
                                key=f"alloc_inp_{inv_id}_{pmt_id}"
                            )
                        with act_c2:
                            notes_val = st.text_input("User Notes / Reason:", value="Verified match", key=f"notes_{inv_id}_{pmt_id}")
                        with act_c3:
                            st.write("")
                            btn_c_conf, btn_c_rej = st.columns(2)
                            with btn_c_conf:
                                if st.button("✅ Confirm", key=f"btn_confirm_{inv_id}_{pmt_id}", type="primary"):
                                    is_valid, err_msg = ReconciliationEngine.validate_allocation(
                                        payment_id=pmt_id,
                                        invoice_id=inv_id,
                                        amount_to_allocate=to_decimal(alloc_val),
                                        payments_df=payments_for_rec,
                                        invoices_df=invoices_for_rec,
                                        confirmed_allocations_df=allocations_df
                                    )
                                    if is_valid:
                                        record_allocation(
                                            invoice_id=inv_id,
                                            payment_id=pmt_id,
                                            allocated_amount=float(alloc_val),
                                            status="CONFIRMED",
                                            user_notes=notes_val
                                        )
                                        st.toast(f"Confirmed allocation of ${alloc_val:,.2f} for {inv_id}!", icon="✅")
                                        st.rerun()
                                    else:
                                        st.error(err_msg)
                            with btn_c_rej:
                                if st.button("❌ Reject", key=f"btn_reject_{inv_id}_{pmt_id}"):
                                    record_allocation(
                                        invoice_id=inv_id,
                                        payment_id=pmt_id,
                                        allocated_amount=0.0,
                                        status="REJECTED",
                                        user_notes=notes_val if notes_val != "Verified match" else "User rejected suggestion"
                                    )
                                    st.toast(f"Rejected suggestion {pmt_id} ⟷ {inv_id}. Decision saved to SQLite.", icon="❌")
                                    st.rerun()
        else:
            st.info("No suggested matches available to review. Run Module 2 matching first.")

    # TAB 2: MANUAL MATCH & CUSTOM ALLOCATION
    with tab_manual_match:
        st.markdown("#### ✍️ Custom Manual Payment Allocation")
        st.markdown("Manually pair any unallocated payment with an invoice. Double allocations are strictly prevented by the balance validator.")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            inv_choices = [
                f"{r['invoice_id']} | {r['customer_name']} | Outstanding: ${r['outstanding_balance']:,.2f}"
                for _, r in invoice_balances_df.iterrows()
            ]
            sel_inv_str = st.selectbox("Select Target Invoice:", inv_choices)
            sel_inv_id = sel_inv_str.split(" | ")[0].strip()
            target_inv_row = invoice_balances_df[invoice_balances_df["invoice_id"] == sel_inv_id].iloc[0]

        with col_m2:
            pmt_choices = [
                f"{r['payment_id']} | {r['customer_name']} | Unallocated: ${r['remaining_unallocated']:,.2f}"
                for _, r in payment_allocations_df.iterrows()
            ]
            sel_pmt_str = st.selectbox("Select Payment Source:", pmt_choices)
            sel_pmt_id = sel_pmt_str.split(" | ")[0].strip()
            source_pmt_row = payment_allocations_df[payment_allocations_df["payment_id"] == sel_pmt_id].iloc[0]

        st.markdown("##### Allocation Details:")
        c_al1, c_al2, c_al3 = st.columns(3)
        with c_al1:
            max_alloc_possible = min(
                float(target_inv_row["outstanding_balance"]),
                float(source_pmt_row["remaining_unallocated"])
            )
            man_amt = st.number_input(
                "Amount to Allocate ($):",
                min_value=0.01,
                max_value=max(0.01, float(source_pmt_row["remaining_unallocated"])),
                value=max(0.01, max_alloc_possible) if max_alloc_possible > 0 else 0.01,
                step=10.0
            )
        with c_al2:
            man_notes = st.text_input("Allocation Memo / Reason:", value="Manual accountant allocation")
        with c_al3:
            st.write("")
            st.write("")
            if st.button("💾 Apply Manual Allocation", type="primary", use_container_width=True):
                is_valid, val_err = ReconciliationEngine.validate_allocation(
                    payment_id=sel_pmt_id,
                    invoice_id=sel_inv_id,
                    amount_to_allocate=to_decimal(man_amt),
                    payments_df=payments_for_rec,
                    invoices_df=invoices_for_rec,
                    confirmed_allocations_df=allocations_df,
                    rejected_pairs=get_rejected_pairs()
                )
                if is_valid:
                    record_allocation(
                        invoice_id=sel_inv_id,
                        payment_id=sel_pmt_id,
                        allocated_amount=float(man_amt),
                        status="CONFIRMED",
                        user_notes=man_notes
                    )
                    st.toast(f"Successfully allocated ${man_amt:,.2f} from {sel_pmt_id} to {sel_inv_id}!", icon="💾")
                    st.rerun()
                else:
                    st.error(val_err)

    # TAB 3: OUTSTANDING BALANCES & RECONCILIATION LEDGER
    with tab_balances:
        st.markdown("#### 📊 Invoice Outstanding Balances Ledger")
        st.markdown("""
        **Exact Balance Formula:**  
        $$\\text{Outstanding Balance} = \\text{Invoice Amount} - \\text{Confirmed Allocations}$$
        Calculated using Python's high-precision `Decimal` to avoid floating-point errors.
        """)

        status_filter = st.selectbox("Filter Invoices by Settlement Status:", ["All", "PAID", "PARTIALLY PAID", "UNPAID"])
        filtered_balances = invoice_balances_df if status_filter == "All" else invoice_balances_df[invoice_balances_df["status"] == status_filter]

        st.dataframe(
            filtered_balances[[
                "invoice_id", "customer_name", "invoice_amount", "confirmed_paid",
                "outstanding_balance", "status", "reconciliation_pct"
            ]],
            column_config={
                "invoice_id": st.column_config.TextColumn("Invoice", width="small"),
                "customer_name": st.column_config.TextColumn("Customer", width="medium"),
                "invoice_amount": st.column_config.NumberColumn("Invoice Amount", format="$%.2f", width="small"),
                "confirmed_paid": st.column_config.NumberColumn("Confirmed Paid", format="$%.2f", width="small"),
                "outstanding_balance": st.column_config.NumberColumn("Outstanding Balance", format="$%.2f", width="small"),
                "status": st.column_config.TextColumn("Status", width="small"),
                "reconciliation_pct": st.column_config.ProgressColumn("% Paid", format="%.0f%%", min_value=0, max_value=100, width="small")
            },
            use_container_width=True
        )

        col_dl_bal, _ = st.columns([2, 4])
        with col_dl_bal:
            bal_csv = invoice_balances_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Outstanding Balances Ledger (CSV)",
                data=bal_csv,
                file_name=f"outstanding_balances_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    # TAB 4: UNRESOLVED TRANSACTIONS & AUDIT LOG
    with tab_unresolved:
        st.markdown("#### ❓ Unresolved Transactions & Decision Audit Trail")

        col_un_inv, col_un_pmt = st.columns(2)
        with col_un_inv:
            st.subheader(f"Unsettled Invoices ({len(unresolved_dict['unsettled_invoices'])})")
            if not unresolved_dict["unsettled_invoices"].empty:
                st.dataframe(
                    unresolved_dict["unsettled_invoices"][["invoice_id", "customer_name", "invoice_amount", "outstanding_balance", "status"]],
                    use_container_width=True
                )
            else:
                st.success("🎉 All invoices are 100% paid!")

        with col_un_pmt:
            st.subheader(f"Unallocated Payments ({len(unresolved_dict['unallocated_payments'])})")
            if not unresolved_dict["unallocated_payments"].empty:
                st.dataframe(
                    unresolved_dict["unallocated_payments"][["payment_id", "customer_name", "payment_amount", "remaining_unallocated", "allocation_status"]],
                    use_container_width=True
                )
            else:
                st.success("🎉 All payments are 100% allocated!")

        st.markdown("---")
        st.markdown("#### 📝 Confirmed Allocations & Rejection Memory Log")
        if not allocations_df.empty:
            st.dataframe(
                allocations_df[["allocation_id", "invoice_id", "payment_id", "allocated_amount", "status", "user_notes", "created_at"]],
                use_container_width=True
            )

            col_del_alc, _ = st.columns([3, 3])
            with col_del_alc:
                sel_del_id = st.selectbox("Select Allocation to Undo / Un-reject:", allocations_df["allocation_id"].tolist())
                if st.button("🗑️ Remove Allocation Record / Reset Decision"):
                    delete_allocation(sel_del_id)
                    st.toast(f"Removed `{sel_del_id}`. Decision reset.", icon="🗑️")
                    st.rerun()
        else:
            st.info("No confirmed or rejected decisions recorded in SQLite yet.")


# ==============================================================================
# VIEW 4: MODULE 4 - DASHBOARD, REPORTING, AND EVALUATION
# ==============================================================================
elif menu_choice == "📈 Module 4: Dashboard, Reporting & Evaluation":
    render_hero_banner(
        title="Module 4: Executive Dashboard & Reporting Suite",
        subtitle="Real-time reconciliation intelligence, ground-truth benchmark analytics, matching precision audits, and decision-support master reports.",
        badge_text="Pipeline Stage 04 • Executive Analytics"
    )
    render_pipeline_stepper(current_step=4)

    # 1. Load active data
    invoices_for_rep = st.session_state.get("m3_invoices_df")
    payments_for_rep = st.session_state.get("m3_payments_df")

    if invoices_for_rep is None or invoices_for_rep.empty:
        db_invs = fetch_table_data("invoices")
        if db_invs:
            invoices_for_rep = pd.DataFrame(db_invs)
        else:
            inv_raw = pd.read_csv(io.StringIO(INVOICE_SAMPLE_CSV))
            invoices_for_rep = validate_records(inv_raw, record_type="invoice")["valid_df"]

    if payments_for_rep is None or payments_for_rep.empty:
        db_pmts = fetch_table_data("payments")
        if db_pmts:
            payments_for_rep = pd.DataFrame(db_pmts)
        else:
            pmt_raw = pd.read_csv(io.StringIO(PAYMENT_SAMPLE_CSV))
            payments_for_rep = validate_records(pmt_raw, record_type="payment")["valid_df"]

    allocations_list = get_allocations()
    allocations_df = pd.DataFrame(allocations_list) if allocations_list else pd.DataFrame(
        columns=["allocation_id", "invoice_id", "payment_id", "allocated_amount", "status", "user_notes", "created_at"]
    )

    matches_data = fetch_table_data("matches")
    if matches_data:
        suggested_matches_df = pd.DataFrame(matches_data)
    elif "match_results" in st.session_state and not st.session_state["match_results"]["matches_df"].empty:
        suggested_matches_df = st.session_state["match_results"]["matches_df"]
    else:
        matcher = IntelligentTransactionMatcher()
        rejected_pairs_set = get_rejected_pairs()
        m_res = matcher.match_transactions(invoices_for_rep, payments_for_rep, rejected_pairs=rejected_pairs_set)
        suggested_matches_df = m_res["matches_df"]

    # 2. Run Ground Truth Evaluation
    eval_output = ReconciliationEvaluator.evaluate_matching(
        suggested_matches_df=suggested_matches_df,
        ground_truth=DEFAULT_GROUND_TRUTH
    )
    eval_metrics = eval_output["metrics"]
    eval_df = eval_output["eval_df"]

    # 3. Calculate Executive Dashboard KPIs
    kpi_summary = ReportGenerator.generate_executive_dashboard_kpis(
        invoices_df=invoices_for_rep,
        payments_df=payments_for_rep,
        matches_df=suggested_matches_df,
        allocations_df=allocations_df,
        eval_metrics=eval_metrics
    )

    # 4. Generate Master Comprehensive Report
    master_report_df = ReportGenerator.generate_comprehensive_reconciliation_report(
        invoices_df=invoices_for_rep,
        payments_df=payments_for_rep,
        matches_df=suggested_matches_df,
        allocations_df=allocations_df
    )

    # --------------------------------------------------------------------------
    # EXECUTIVE KPI DASHBOARD SECTION (High-Impact SaaS Grid)
    # --------------------------------------------------------------------------
    st.markdown("### 🏛️ Executive Reconciliation Metrics")

    eq1, eq2, eq3, eq4 = st.columns(4)
    with eq1:
        st.markdown(render_kpi_card_html("Total Invoices", str(kpi_summary["total_invoices"]), f"${kpi_summary['total_invoice_amount']:,.2f} Book Value", "📄", "indigo"), unsafe_allow_html=True)
    with eq2:
        st.markdown(render_kpi_card_html("Total Payments", str(kpi_summary["total_payments"]), f"${kpi_summary['total_payment_amount']:,.2f} Total Inflow", "💳", "sky", "#F0F9FF"), unsafe_allow_html=True)
    with eq3:
        st.markdown(render_kpi_card_html("Confirmed Matches", str(kpi_summary["confirmed_matches"]), f"${kpi_summary['total_confirmed_paid']:,.2f} Confirmed", "✅", "emerald", "#ECFDF5"), unsafe_allow_html=True)
    with eq4:
        st.markdown(render_kpi_card_html("Review Required", str(kpi_summary["cases_requiring_review"]), "Discrepancies flagged", "⚠️", "rose", "#FEF2F2"), unsafe_allow_html=True)

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    eq5, eq6, eq7, eq8 = st.columns(4)
    with eq5:
        st.markdown(render_kpi_card_html("Unmatched Invoices", str(kpi_summary["unmatched_invoices"]), "Uncollected balance", "⏳", "amber", "#FFFBEB"), unsafe_allow_html=True)
    with eq6:
        st.markdown(render_kpi_card_html("Unallocated Funds", str(kpi_summary["unallocated_payments"]), "Unassigned cash", "❓", "indigo"), unsafe_allow_html=True)
    with eq7:
        st.markdown(render_kpi_card_html("Matching Precision", f"{kpi_summary['matching_precision_pct']:.1f}%", "Ground-truth evaluated", "🎯", "emerald", "#ECFDF5"), unsafe_allow_html=True)
    with eq8:
        st.markdown(render_kpi_card_html("Settlement Rate", f"{kpi_summary['reconciliation_settlement_rate']:.1f}%", f"${kpi_summary['total_outstanding_balance']:,.2f} Outstanding", "📈", "sky", "#F0F9FF"), unsafe_allow_html=True)

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

    # Executive Charts Section
    m4_ch1, m4_ch2 = st.columns(2)
    with m4_ch1:
        st.markdown("<div class='chart-box'><div class='chart-title'>📊 Portfolio Settlement Status Breakdown</div>", unsafe_allow_html=True)
        invoice_balances_df = ReconciliationEngine.calculate_invoice_balances(invoices_for_rep, allocations_df)
        d_chart = get_settlement_donut_chart(invoice_balances_df)
        if d_chart:
            st.altair_chart(d_chart, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with m4_ch2:
        st.markdown("<div class='chart-box'><div class='chart-title'>💰 Gross Receivable vs Collections Comparison</div>", unsafe_allow_html=True)
        b_chart = get_financial_breakdown_bar_chart(
            kpi_summary['total_invoice_amount'],
            kpi_summary['total_confirmed_paid'],
            kpi_summary['total_outstanding_balance']
        )
        st.altair_chart(b_chart, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Navigation Tabs for Module 4
    tab_master_rep, tab_benchmark, tab_discrepancies, tab_kpi_table = st.tabs([
        "📑 1. Comprehensive Reconciliation Report",
        "🎯 2. Ground-Truth Benchmark & Precision Analytics",
        "⚠️ 3. Discrepancies & Unresolved Cases",
        "📊 4. Executive KPI Summary Table"
    ])

    # TAB 1: MASTER RECONCILIATION REPORT
    with tab_master_rep:
        st.markdown("#### 📑 Master Reconciliation Audit Report")
        st.markdown("""
        Unified report combining invoices, payments, match decisions, RapidFuzz confidence scores,
        supporting explanations, allocated amounts, and outstanding balances.
        """)

        rep_filter = st.selectbox(
            "Filter Report Records:",
            ["All Records", "Unresolved / Action Needed", "Fully Reconciled & Confirmed"]
        )

        if rep_filter == "Unresolved / Action Needed":
            display_rep = master_report_df[master_report_df["is_unresolved"] == True]
        elif rep_filter == "Fully Reconciled & Confirmed":
            display_rep = master_report_df[master_report_df["is_unresolved"] == False]
        else:
            display_rep = master_report_df

        st.dataframe(
            display_rep[[
                "invoice_id", "customer_name", "invoice_amount", "payment_id", "payment_amount",
                "amount_difference", "match_decision", "confidence_level", "confidence_score",
                "matching_evidence", "invoice_outstanding_balance", "invoice_status"
            ]],
            column_config={
                "invoice_id": st.column_config.TextColumn("Invoice", width="small"),
                "customer_name": st.column_config.TextColumn("Customer", width="medium"),
                "invoice_amount": st.column_config.NumberColumn("Inv Amt", format="$%.2f", width="small"),
                "payment_id": st.column_config.TextColumn("Payment", width="small"),
                "payment_amount": st.column_config.NumberColumn("Paid Amt", format="$%.2f", width="small"),
                "amount_difference": st.column_config.NumberColumn("Diff", format="$%.2f", width="small"),
                "match_decision": st.column_config.TextColumn("Decision", width="small"),
                "confidence_level": st.column_config.TextColumn("Confidence", width="small"),
                "confidence_score": st.column_config.NumberColumn("Score", format="%.0f", width="small"),
                "matching_evidence": st.column_config.TextColumn("Evidence & Explanation", width="large"),
                "invoice_outstanding_balance": st.column_config.NumberColumn("Outstanding", format="$%.2f", width="small"),
                "invoice_status": st.column_config.TextColumn("Status", width="small")
            },
            use_container_width=True
        )

        col_dl_master, col_dl_kpi = st.columns([2, 2])
        with col_dl_master:
            csv_master = master_report_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Comprehensive Reconciliation Report (CSV)",
                data=csv_master,
                file_name=f"comprehensive_reconciliation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

        with col_dl_kpi:
            kpi_df = pd.DataFrame([kpi_summary])
            csv_kpi = kpi_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Executive KPI Summary (CSV)",
                data=csv_kpi,
                file_name=f"executive_reconciliation_kpi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    # TAB 2: GROUND-TRUTH BENCHMARK & PRECISION ANALYTICS
    with tab_benchmark:
        st.markdown("#### 🎯 Ground-Truth Benchmark Evaluation")
        st.markdown("""
        Evaluates matching algorithm accuracy against a labeled dataset to verify:
        - **Precision**: $\\frac{\\text{True Positives}}{\\text{Total Suggested Matches}}$
        - **Recall**: $\\frac{\\text{True Positives}}{\\text{Total Expected Matches}}$
        - **Correct Suggestion Rate**: Proportion of records receiving correct suggestions.
        """)

        bm1, bm2, bm3, bm4 = st.columns(4)
        with bm1:
            st.markdown(render_kpi_card_html("Precision", f"{eval_metrics['precision']:.1f}%", "TP / (TP + FP)", "🎯", "emerald", "#ECFDF5"), unsafe_allow_html=True)
        with bm2:
            st.markdown(render_kpi_card_html("Recall", f"{eval_metrics['recall']:.1f}%", "TP / (TP + FN)", "🔍", "sky", "#F0F9FF"), unsafe_allow_html=True)
        with bm3:
            st.markdown(render_kpi_card_html("F1 Score", f"{eval_metrics['f1_score']:.1f}%", "Harmonic Mean", "⚖️", "indigo"), unsafe_allow_html=True)
        with bm4:
            st.markdown(render_kpi_card_html("Accuracy", f"{eval_metrics['correct_suggestion_rate']:.1f}%", "Correct Pair Rate", "🏆", "emerald", "#ECFDF5"), unsafe_allow_html=True)

        st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)
        st.markdown("##### Detailed Benchmark Classification:")
        st.dataframe(
            eval_df[[
                "payment_id", "expected_invoice", "suggested_invoice", "outcome",
                "confidence", "confidence_score", "matching_evidence", "notes"
            ]],
            column_config={
                "payment_id": st.column_config.TextColumn("Payment ID", width="small"),
                "expected_invoice": st.column_config.TextColumn("Ground Truth Target", width="small"),
                "suggested_invoice": st.column_config.TextColumn("Algorithm Suggestion", width="small"),
                "outcome": st.column_config.TextColumn("Classification Outcome", width="medium"),
                "confidence": st.column_config.TextColumn("Confidence", width="small"),
                "confidence_score": st.column_config.NumberColumn("Score", format="%.0f", width="small"),
                "matching_evidence": st.column_config.TextColumn("Evidence", width="medium"),
                "notes": st.column_config.TextColumn("Evaluation Notes", width="large")
            },
            use_container_width=True
        )

        col_dl_eval, _ = st.columns([2, 4])
        with col_dl_eval:
            csv_eval = eval_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download Ground Truth Benchmark Report (CSV)",
                data=csv_eval,
                file_name=f"ground_truth_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

    # TAB 3: DISCREPANCIES & UNRESOLVED CASES
    with tab_discrepancies:
        st.markdown("#### ⚠️ Discrepancies & Unresolved Cases Breakdown")
        st.markdown("List of transactions that require accountant action, investigation, or manual adjustment.")

        unresolved_records = master_report_df[master_report_df["is_unresolved"] == True]

        if not unresolved_records.empty:
            st.warning(f"Found {len(unresolved_records)} unresolved record(s) requiring attention.")
            st.dataframe(
                unresolved_records[[
                    "invoice_id", "payment_id", "customer_name", "invoice_amount",
                    "payment_amount", "amount_difference", "match_decision",
                    "review_flags", "invoice_outstanding_balance", "invoice_status"
                ]],
                use_container_width=True
            )

            col_dl_unres, _ = st.columns([2, 4])
            with col_dl_unres:
                csv_unres = unresolved_records.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download Unresolved Transactions Report (CSV)",
                    data=csv_unres,
                    file_name=f"unresolved_discrepancies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.success("🎉 Outstanding balance is $0.00 and all payments are fully matched! No unresolved discrepancies.")

    # TAB 4: EXECUTIVE KPI SUMMARY TABLE (Matches Prompt Table Example)
    with tab_kpi_table:
        st.markdown("#### 📊 Executive KPI Summary Table (Standard Dashboard Format)")
        
        prompt_example_table = pd.DataFrame([
            {"Metric": "Total invoices", "Result": str(kpi_summary["total_invoices"]), "Benchmark Note": "Total registered invoice records"},
            {"Metric": "Total payments", "Result": str(kpi_summary["total_payments"]), "Benchmark Note": "Total registered payment records"},
            {"Metric": "Confirmed matches", "Result": str(kpi_summary["confirmed_matches"]), "Benchmark Note": "Officially confirmed pairings"},
            {"Metric": "Unmatched invoices", "Result": str(kpi_summary["unmatched_invoices"]), "Benchmark Note": "Invoices with unpaid balance > $0"},
            {"Metric": "Unallocated payments", "Result": str(kpi_summary["unallocated_payments"]), "Benchmark Note": "Payments with remaining unassigned funds"},
            {"Metric": "Cases requiring review", "Result": str(kpi_summary["cases_requiring_review"]), "Benchmark Note": "Discrepancies & ambiguous candidates"},
            {"Metric": "Matching precision", "Result": f"{kpi_summary['matching_precision_pct']:.1f}%", "Benchmark Note": "True positive suggestions / Total suggestions"},
            {"Metric": "Correct suggestion rate", "Result": f"{kpi_summary['correct_suggestion_pct']:.1f}%", "Benchmark Note": "Overall correct pair assignment rate"},
            {"Metric": "Total Invoiced Amount", "Result": f"${kpi_summary['total_invoice_amount']:,.2f}", "Benchmark Note": "Gross invoice book value"},
            {"Metric": "Total Confirmed Paid", "Result": f"${kpi_summary['total_confirmed_paid']:,.2f}", "Benchmark Note": "Settled funds collected"},
            {"Metric": "Total Outstanding Balance", "Result": f"${kpi_summary['total_outstanding_balance']:,.2f}", "Benchmark Note": "Total uncollected receivable"}
        ])

        st.table(prompt_example_table)


# ==============================================================================
# VIEW 5: SQLITE DATABASE EXPLORER
# ==============================================================================
elif menu_choice == "🗄️ SQLite Database Explorer":
    render_hero_banner(
        title="SQLite Database Explorer & Auditor",
        subtitle="Direct inspection of underlying SQLite relational tables, schema definitions, audit logs, and transaction status queries.",
        badge_text="System Administration • DB Inspector"
    )

    db_stats = get_database_stats()
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(render_kpi_card_html("Invoices Table", str(db_stats["total_invoices"]), f"${db_stats['total_invoice_amount']:,.2f}", "📄", "indigo"), unsafe_allow_html=True)
    with c2:
        st.markdown(render_kpi_card_html("Payments Table", str(db_stats["total_payments"]), f"${db_stats['total_payment_amount']:,.2f}", "💳", "sky", "#F0F9FF"), unsafe_allow_html=True)
    with c3:
        st.markdown(render_kpi_card_html("Matches Table", str(db_stats.get("total_matches", 0)), "Proposed pairings", "🎯", "indigo"), unsafe_allow_html=True)
    with c4:
        st.markdown(render_kpi_card_html("Allocations", str(db_stats.get("confirmed_allocations_count", 0)), "Confirmed allocations", "✅", "emerald", "#ECFDF5"), unsafe_allow_html=True)
    with c5:
        st.markdown(render_kpi_card_html("Rejections", str(db_stats.get("rejected_allocations_count", 0)), "User rejections memory", "❌", "rose", "#FEF2F2"), unsafe_allow_html=True)

    st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

    tab_inv, tab_pmt, tab_mch, tab_alc, tab_err = st.tabs([
        "📄 Stored Invoices",
        "💳 Stored Payments",
        "🎯 Stored Matches",
        "⚖️ Allocations & Decisions",
        "📋 Rejection Audit Logs"
    ])

    with tab_inv:
        invoices_data = fetch_table_data("invoices")
        if invoices_data:
            df_inv = pd.DataFrame(invoices_data)
            st.dataframe(df_inv, use_container_width=True)
            st.download_button(
                "📥 Export Invoices (CSV)",
                data=df_inv.to_csv(index=False).encode("utf-8"),
                file_name="sqlite_invoices.csv",
                mime="text/csv"
            )
        else:
            st.info("No invoice records in SQLite database yet. Import some invoices using Module 1.")

    with tab_pmt:
        payments_data = fetch_table_data("payments")
        if payments_data:
            df_pmt = pd.DataFrame(payments_data)
            st.dataframe(df_pmt, use_container_width=True)
            st.download_button(
                "📥 Export Payments (CSV)",
                data=df_pmt.to_csv(index=False).encode("utf-8"),
                file_name="sqlite_payments.csv",
                mime="text/csv"
            )
        else:
            st.info("No payment records in SQLite database yet.")

    with tab_mch:
        matches_data = fetch_table_data("matches")
        if matches_data:
            df_m = pd.DataFrame(matches_data)
            st.dataframe(df_m, use_container_width=True)
        else:
            st.info("No transaction matches saved in SQLite database yet.")

    with tab_alc:
        alloc_data = fetch_table_data("allocations")
        if alloc_data:
            df_a = pd.DataFrame(alloc_data)
            st.dataframe(df_a, use_container_width=True)
            st.download_button(
                "📥 Export Allocations (CSV)",
                data=df_a.to_csv(index=False).encode("utf-8"),
                file_name="sqlite_allocations.csv",
                mime="text/csv"
            )
        else:
            st.info("No confirmed allocations in SQLite yet. Use Module 3 to confirm matches.")

    with tab_err:
        errors_data = fetch_table_data("invalid_records")
        if errors_data:
            df_err = pd.DataFrame(errors_data)
            st.dataframe(df_err, use_container_width=True)
        else:
            st.info("Audit log is currently empty.")

    st.markdown("---")
    st.markdown("### ⚠️ Database Management")
    with st.expander("Danger Zone: Reset Database", expanded=False):
        st.warning("Resetting the database will drop and recreate all tables (invoices, payments, matches, allocations, invalid_records).")
        if st.button("🗑️ Reset & Clear SQLite Database", type="secondary"):
            reset_database()
            st.toast("SQLite database has been reset.", icon="🗑️")
            st.rerun()


# ==============================================================================
# VIEW 6: DOWNLOAD SAMPLE CSVS
# ==============================================================================
elif menu_choice == "🧪 Download Sample CSVs":
    render_hero_banner(
        title="Benchmark Datasets & Sample Files",
        subtitle="Ready-to-use CSV test files containing realistic scenarios: exact reference matches, RapidFuzz name variations, amount discrepancies, and edge cases.",
        badge_text="Resources • Test Data"
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📄 Sample Invoices CSV")
        st.markdown("""
        Contains:
        - 🎯 `INV-101`: Acme Corp, $5,000 (Matches PAY-201 -> Outstanding $0)
        - 🎯 `INV-102`: Global Logistics LLC, $3,000 (Matches PAY-202 -> Outstanding $1,000)
        - 🎯 `INV-103`: Apex Innovations Inc., $7,000 (Unpaid -> Outstanding $7,000)
        - ✅ Messy customer names & multiple date formats
        - ❌ Intentionally invalid rows for Module 1 testing
        """)
        st.download_button(
            "📥 Download sample_invoices.csv",
            data=INVOICE_SAMPLE_CSV.strip(),
            file_name="sample_invoices.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        st.subheader("💳 Sample Payments CSV")
        st.markdown("""
        Contains:
        - 🎯 `PAY-201`: Linked to INV-101, $5,000 (Full settlement)
        - 🎯 `PAY-202`: Global Logistics, $3,000 (Allocates $2,000 to INV-102, $1,000 remaining)
        - 🎯 `PAY-203`: Linked to INV-103, $6,500 (Discrepancy test)
        - ❌ Intentionally invalid rows for Module 1 testing
        """)
        st.download_button(
            "📥 Download sample_payments.csv",
            data=PAYMENT_SAMPLE_CSV.strip(),
            file_name="sample_payments.csv",
            mime="text/csv",
            use_container_width=True
        )


# ==============================================================================
# VIEW 7: RULES & SCHEMA REFERENCE
# ==============================================================================
elif menu_choice == "📋 Rules & Architecture Reference":
    render_hero_banner(
        title="Architecture & Algorithmic Rules",
        subtitle="Complete technical documentation for validation, RapidFuzz scoring weights, Decimal reconciliation rules, and ground-truth evaluation mathematics.",
        badge_text="Documentation • Architecture Spec"
    )

    st.markdown("""
    ### Module 1: Validation & Normalization
    - **Customer Names**: Cleans trailing punctuation, strips multiple spaces, Title-cases.
    - **Transaction Dates**: Parsed from formats (`YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, `05-Feb-2024`) into ISO `YYYY-MM-DD`.
    - **Amounts**: Currency symbols (`$`, `€`, `₹`, `£`) stripped, parsed to float, verified `> 0`.
    - **Duplicates**: Checked within CSV file and against existing primary keys in SQLite.

    ---

    ### Module 2: Intelligent Matching Matrix
    | Dimension | Weight | Criteria & Evaluation |
    | :--- | :---: | :--- |
    | **Invoice Reference** | 40 pts | Exact reference match or extracted from payment description |
    | **Customer Name (RapidFuzz)** | 30 pts | Token sort ratio compares customer names; legal suffixes stripped |
    | **Amount Comparison** | 20 pts | Exact amount match awards full points; discrepancies flagged |
    | **Date Plausibility** | 10 pts | Evaluates settlement window; flags payments predating invoice issue date |

    ---

    ### Module 3: Reconciliation & Decimal Balance Rules
    - **Exact Outstanding Balance Formula:**
      $$\\text{Outstanding Balance} = \\text{Invoice Amount} - \\text{Confirmed Allocations}$$
    - **Settlement Categories:**
      - **PAID**: Outstanding Balance = $0.00
      - **PARTIALLY PAID**: $0.00 < Outstanding Balance < Invoice Amount
      - **UNPAID**: Confirmed Paid = $0.00
      - **OVERPAID**: Confirmed Paid > Invoice Amount
    - **Anti-Double-Allocation Guard:**
      - Tracks allocated amount per payment: $\\sum \\text{allocated} \\le \\text{payment\\_amount}$.
      - Rejects any allocation exceeding remaining unallocated capacity.
    - **Rejection Memory:**
      - Persists user rejections in SQLite `allocations` table (`status='REJECTED'`).
      - Matcher loads rejected pairs and guarantees they are never silently reintroduced.

    ---

    ### Module 4: Dashboard, Reporting & Evaluation
    - **Executive KPI Dashboard**: Displays total invoices, payments, confirmed matches, unmatched items, precision, and financial balances.
    - **Ground-Truth Benchmark**: Evaluates matching Precision, Recall, and Accuracy against ground-truth labels.
    - **Exportable Reports**: Master Reconciliation CSV, Executive KPI CSV, Unresolved Discrepancies CSV.
    """)
