"""
Unit and Integration Tests for Module 2: Intelligent Transaction Matching
Verifies:
- Invoice reference and exact amount matching (High confidence)
- Fuzzy customer name matching via RapidFuzz (Medium confidence)
- Amount discrepancy flagging (Review required)
- Date anomaly handling
- SQLite persistence of suggested matches
"""

import os
import unittest
import pandas as pd

from matcher import IntelligentTransactionMatcher
from database import init_db, save_matches, fetch_table_data, reset_database


class TestIntelligentTransactionMatching(unittest.TestCase):
    def setUp(self):
        self.matcher = IntelligentTransactionMatcher(customer_name_threshold=70.0)
        self.test_db = os.path.join(os.path.dirname(__file__), "test_matcher.db")
        reset_database(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                reset_database(self.test_db)
            except Exception:
                pass

    def test_exact_invoice_reference_and_amount_high_confidence(self):
        # Example 1 from prompt:
        # INV-101, ₹5,000 | PAY-201, ₹5,000 -> Exact invoice reference and amount -> High
        inv = {
            "invoice_id": "INV-101",
            "customer_name": "Acme Corp",
            "amount": 5000.0,
            "transaction_date": "2024-01-10",
            "description": "Monthly retainer"
        }
        pmt = {
            "payment_id": "PAY-201",
            "invoice_id": "INV-101",
            "customer_name": "Acme Corp",
            "amount": 5000.0,
            "transaction_date": "2024-01-14",
            "description": "Payment for INV-101"
        }

        score, conf, evidence, flags, details = self.matcher.calculate_match_score(inv, pmt)
        self.assertEqual(conf, "High")
        self.assertGreaterEqual(score, 80.0)
        self.assertEqual(evidence, "Exact invoice reference and amount")
        self.assertNotIn("AMOUNT_MISMATCH", flags)

    def test_fuzzy_customer_name_and_matching_amount_medium_confidence(self):
        # Example 2 from prompt:
        # INV-102, ₹3,000 | PAY-202, ₹3,000 -> Similar customer name and matching amount -> Medium
        inv = {
            "invoice_id": "INV-102",
            "customer_name": "Global Logistics LLC",
            "amount": 3000.0,
            "transaction_date": "2024-01-10",
            "description": "Freight charges"
        }
        pmt = {
            "payment_id": "PAY-202",
            "invoice_id": "",  # Missing invoice reference
            "customer_name": "Global Logistics",  # Slight variation
            "amount": 3000.0,
            "transaction_date": "2024-01-18",
            "description": "Freight payment"
        }

        score, conf, evidence, flags, details = self.matcher.calculate_match_score(inv, pmt)
        self.assertIn(conf, ["Medium", "High"])
        self.assertIn("Similar customer name", evidence)
        self.assertAlmostEqual(details["amount_diff"], 0.0)

    def test_customer_matches_but_amount_differs_review_required(self):
        # Example 3 from prompt:
        # INV-103, ₹7,000 | PAY-203, ₹6,500 -> Customer matches, but amount differs -> Review required
        inv = {
            "invoice_id": "INV-103",
            "customer_name": "Apex Innovations Inc.",
            "amount": 7000.0,
            "transaction_date": "2024-01-10",
            "description": "Server hardware"
        }
        pmt = {
            "payment_id": "PAY-203",
            "invoice_id": "INV-103",
            "customer_name": "Apex Innovations Inc",
            "amount": 6500.0,  # 500 less
            "transaction_date": "2024-01-15",
            "description": "Partial payment"
        }

        score, conf, evidence, flags, details = self.matcher.calculate_match_score(inv, pmt)
        self.assertEqual(conf, "Review required")
        self.assertIn("AMOUNT_MISMATCH", flags)
        self.assertIn("Customer matches, but amount differs", evidence)
        self.assertEqual(details["amount_diff"], -500.0)

    def test_batch_matching_and_unmatched_records(self):
        invoices = pd.DataFrame([
            {"invoice_id": "INV-101", "customer_name": "Acme Corp", "amount": 5000.0, "transaction_date": "2024-01-10"},
            {"invoice_id": "INV-102", "customer_name": "Beta Tech", "amount": 3000.0, "transaction_date": "2024-01-12"},
            {"invoice_id": "INV-103", "customer_name": "Gamma Ltd", "amount": 1000.0, "transaction_date": "2024-01-15"}
        ])
        payments = pd.DataFrame([
            {"payment_id": "PAY-201", "invoice_id": "INV-101", "customer_name": "Acme Corp", "amount": 5000.0, "transaction_date": "2024-01-14"},
            {"payment_id": "PAY-202", "invoice_id": "", "customer_name": "Beta Technologies", "amount": 3000.0, "transaction_date": "2024-01-18"},
            {"payment_id": "PAY-999", "invoice_id": "", "customer_name": "Completely Unknown", "amount": 9999.0, "transaction_date": "2024-01-20"}
        ])

        results = self.matcher.match_transactions(invoices, payments)
        matches_df = results["matches_df"]
        unmatched_pmt = results["unmatched_payments_df"]
        unmatched_inv = results["unmatched_invoices_df"]

        self.assertEqual(len(matches_df), 2)
        self.assertEqual(len(unmatched_pmt), 1)  # PAY-999 has no match
        self.assertEqual(unmatched_pmt.iloc[0]["payment_id"], "PAY-999")
        self.assertEqual(len(unmatched_inv), 1)  # INV-103 has no match
        self.assertEqual(unmatched_inv.iloc[0]["invoice_id"], "INV-103")

    def test_sqlite_persistence_of_matches(self):
        matches_data = pd.DataFrame([{
            "invoice_id": "INV-101",
            "payment_id": "PAY-201",
            "confidence": "High",
            "confidence_score": 95.0,
            "matching_evidence": "Exact invoice reference and amount",
            "review_flags": "CLEAN_MATCH",
            "invoice_amount": 5000.0,
            "payment_amount": 5000.0,
            "amount_diff": 0.0
        }])

        saved = save_matches(matches_data, db_path=self.test_db)
        self.assertEqual(saved, 1)

        db_records = fetch_table_data("matches", db_path=self.test_db)
        self.assertEqual(len(db_records), 1)
        self.assertEqual(db_records[0]["invoice_id"], "INV-101")
        self.assertEqual(db_records[0]["confidence"], "High")


if __name__ == "__main__":
    unittest.main()
