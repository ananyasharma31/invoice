"""
Test Suite for Module 4: Dashboard, Reporting, and Evaluation
Written with pytest to verify:
- Matching precision, recall, and correct suggestion rate calculation
- Ground-truth evaluation benchmarks
- Generation of comprehensive, decision-support reconciliation CSV reports
- Executive dashboard KPI aggregation
"""

import pytest
import pandas as pd
from decimal import Decimal

from evaluation import ReconciliationEvaluator, ReportGenerator, DEFAULT_GROUND_TRUTH


def test_ground_truth_matching_evaluation():
    # Mock suggested matches dataframe
    suggested_df = pd.DataFrame([
        {"payment_id": "PAY-201", "invoice_id": "INV-101", "confidence": "High", "confidence_score": 95.0, "matching_evidence": "Exact match"},
        {"payment_id": "PAY-202", "invoice_id": "INV-102", "confidence": "Medium", "confidence_score": 80.0, "matching_evidence": "Fuzzy customer"},
        {"payment_id": "PAY-203", "invoice_id": "INV-103", "confidence": "Review required", "confidence_score": 60.0, "matching_evidence": "Amount discrepancy"},
        {"payment_id": "PAY-999", "invoice_id": "INV-888", "confidence": "Low", "confidence_score": 40.0, "matching_evidence": "Weak correlation"}
    ])

    ground_truth = {
        "PAY-201": "INV-101",  # True Positive
        "PAY-202": "INV-102",  # True Positive
        "PAY-203": "INV-103",  # True Positive
        "PAY-404": "INV-404"   # False Negative (missed by algorithm)
        # PAY-999 is a False Positive (suggested but not in ground truth)
    }

    eval_result = ReconciliationEvaluator.evaluate_matching(suggested_df, ground_truth=ground_truth)
    metrics = eval_result["metrics"]
    eval_df = eval_result["eval_df"]

    # TP = 3, FP = 1, FN = 1
    assert metrics["true_positives"] == 3
    assert metrics["false_positives"] == 1
    assert metrics["false_negatives"] == 1

    # Precision = 3 / (3 + 1) = 75.0%
    assert metrics["precision"] == 75.0
    # Recall = 3 / (3 + 1) = 75.0%
    assert metrics["recall"] == 75.0

    assert not eval_df.empty
    assert "outcome" in eval_df.columns


def test_comprehensive_reconciliation_report_generation():
    invoices_df = pd.DataFrame([
        {"invoice_id": "INV-101", "customer_name": "Acme Corp", "amount": 5000.0, "transaction_date": "2024-01-10"},
        {"invoice_id": "INV-102", "customer_name": "Global Logistics", "amount": 3000.0, "transaction_date": "2024-01-12"},
        {"invoice_id": "INV-103", "customer_name": "Apex Innovations", "amount": 7000.0, "transaction_date": "2024-01-15"}
    ])

    payments_df = pd.DataFrame([
        {"payment_id": "PAY-201", "customer_name": "Acme Corp", "amount": 5000.0, "transaction_date": "2024-01-14"},
        {"payment_id": "PAY-202", "customer_name": "Global Logistics", "amount": 2000.0, "transaction_date": "2024-01-18"},
        {"payment_id": "PAY-999", "customer_name": "Orphan Payer", "amount": 1000.0, "transaction_date": "2024-01-20"}
    ])

    matches_df = pd.DataFrame([
        {"invoice_id": "INV-101", "payment_id": "PAY-201", "confidence": "High", "confidence_score": 95.0, "matching_evidence": "Exact match", "review_flags": "CLEAN"},
        {"invoice_id": "INV-102", "payment_id": "PAY-202", "confidence": "Medium", "confidence_score": 80.0, "matching_evidence": "Partial amount", "review_flags": "PARTIAL"}
    ])

    allocations_df = pd.DataFrame([
        {"invoice_id": "INV-101", "payment_id": "PAY-201", "allocated_amount": 5000.0, "status": "CONFIRMED", "user_notes": "Approved", "created_at": "2024-01-15"},
        {"invoice_id": "INV-102", "payment_id": "PAY-202", "allocated_amount": 2000.0, "status": "CONFIRMED", "user_notes": "Partial", "created_at": "2024-01-19"}
    ])

    report_df = ReportGenerator.generate_comprehensive_reconciliation_report(
        invoices_df, payments_df, matches_df, allocations_df
    )

    required_columns = [
        "invoice_id", "customer_name", "invoice_amount", "payment_id", "payment_amount",
        "amount_difference", "match_decision", "confidence_level", "confidence_score",
        "matching_evidence", "invoice_outstanding_balance", "invoice_status", "is_unresolved"
    ]
    for col in required_columns:
        assert col in report_df.columns

    # Verify INV-101 is marked PAID with 0 outstanding balance
    inv101_row = report_df[report_df["invoice_id"] == "INV-101"].iloc[0]
    assert inv101_row["invoice_status"] == "PAID"
    assert inv101_row["invoice_outstanding_balance"] == 0.0

    # Verify INV-102 is marked PARTIALLY PAID with 1,000 outstanding balance
    inv102_row = report_df[report_df["invoice_id"] == "INV-102"].iloc[0]
    assert inv102_row["invoice_status"] == "PARTIALLY PAID"
    assert inv102_row["invoice_outstanding_balance"] == 1000.0

    # Verify PAY-999 is listed as an UNALLOCATED / UNMATCHED record
    orphan_row = report_df[report_df["payment_id"] == "PAY-999"].iloc[0]
    assert orphan_row["match_decision"] == "UNALLOCATED"
    assert bool(orphan_row["is_unresolved"]) is True


def test_executive_kpi_metrics():
    invoices_df = pd.DataFrame([{"invoice_id": "I1", "amount": 100.0}, {"invoice_id": "I2", "amount": 200.0}])
    payments_df = pd.DataFrame([{"payment_id": "P1", "amount": 100.0}])
    allocations_df = pd.DataFrame([{"invoice_id": "I1", "payment_id": "P1", "allocated_amount": 100.0, "status": "CONFIRMED"}])

    kpis = ReportGenerator.generate_executive_dashboard_kpis(
        invoices_df=invoices_df,
        payments_df=payments_df,
        matches_df=pd.DataFrame(),
        allocations_df=allocations_df,
        eval_metrics={"precision": 95.0, "correct_suggestion_rate": 90.0}
    )

    assert kpis["total_invoices"] == 2
    assert kpis["total_payments"] == 1
    assert kpis["confirmed_matches"] == 1
    assert kpis["total_invoice_amount"] == 300.0
    assert kpis["total_confirmed_paid"] == 100.0
    assert kpis["total_outstanding_balance"] == 200.0
    assert kpis["matching_precision_pct"] == 95.0
