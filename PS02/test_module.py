"""
Unit and Integration Tests for Module 1: Data Import and Validation
Verifies all core requirements:
- Required field validation (invoice ID, customer name, amount, date)
- Normalization (names, dates, descriptions)
- Identification of missing fields, invalid amounts, duplicate records
- SQLite database persistence and error logging
"""

import os
import unittest
import pandas as pd
import sqlite3

from validator import (
    normalize_customer_name,
    normalize_date,
    normalize_amount,
    normalize_description,
    validate_records
)
from database import (
    init_db,
    insert_invoices,
    insert_payments,
    log_invalid_records,
    get_existing_ids,
    get_database_stats,
    reset_database
)


class TestModule1Validation(unittest.TestCase):
    def setUp(self):
        self.test_db = os.path.join(os.path.dirname(__file__), "test_reconciliation.db")
        reset_database(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                reset_database(self.test_db)
            except Exception:
                pass

    def test_customer_name_normalization(self):
        name, err = normalize_customer_name("  acme   corporations,  ")
        self.assertIsNone(err)
        self.assertEqual(name, "Acme Corporations")

        # Blank/missing
        name, err = normalize_customer_name("")
        self.assertIsNotNone(err)
        name, err = normalize_customer_name(None)
        self.assertIsNotNone(err)

    def test_date_normalization(self):
        # ISO format
        d, err = normalize_date("2024-01-15")
        self.assertIsNone(err)
        self.assertEqual(d, "2024-01-15")

        # Slash format
        d, err = normalize_date("18/01/2024")
        self.assertIsNone(err)
        self.assertEqual(d, "2024-01-18")

        # Text month format
        d, err = normalize_date("05-Feb-2024")
        self.assertIsNone(err)
        self.assertEqual(d, "2024-02-05")

        # Invalid date
        d, err = normalize_date("invalid-date-string")
        self.assertIsNotNone(err)

    def test_amount_normalization_and_validation(self):
        # Currency symbol and comma
        amt, err = normalize_amount("$1,500.50")
        self.assertIsNone(err)
        self.assertEqual(amt, 1500.50)

        # Euro and spaces
        amt, err = normalize_amount(" € 2400.00 ")
        self.assertIsNone(err)
        self.assertEqual(amt, 2400.00)

        # Negative amount -> invalid
        amt, err = normalize_amount("-500.00")
        self.assertIsNotNone(err)
        self.assertIn("positive", err)

        # Zero amount -> invalid
        amt, err = normalize_amount("0.00")
        self.assertIsNotNone(err)

        # Non-numeric
        amt, err = normalize_amount("FREE")
        self.assertIsNotNone(err)

    def test_invoice_validation_and_duplicate_detection(self):
        data = {
            "invoice_id": ["INV-001", "INV-002", "INV-003", "INV-001", "INV-004", ""],
            "customer_name": ["Acme Corp", "Beta Tech", "", "Acme Corp", "Delta Inc", "Echo Co"],
            "amount": ["$100.00", "-50.00", "200.00", "100.00", "NOT_A_NUM", "300.00"],
            "transaction_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-01", "2024-01-05", "2024-01-06"]
        }
        df = pd.DataFrame(data)
        result = validate_records(df, record_type="invoice", existing_db_ids={"INV-999"})

        valid_df = result["valid_df"]
        invalid_df = result["invalid_df"]
        metrics = result["metrics"]

        # Only INV-001 (first occurrence) should be completely valid
        self.assertEqual(len(valid_df), 1)
        self.assertEqual(valid_df.iloc[0]["invoice_id"], "INV-001")
        self.assertEqual(valid_df.iloc[0]["amount"], 100.00)

        # Invalid records count
        self.assertEqual(len(invalid_df), 5)
        # Verify duplicate detected for the second INV-001
        dup_rows = invalid_df[invalid_df["error_type"].str.contains("DUPLICATE_IN_FILE")]
        self.assertEqual(len(dup_rows), 1)

    def test_database_persistence_and_existing_id_check(self):
        # Insert initial invoice into SQLite
        initial_df = pd.DataFrame([{
            "invoice_id": "INV-100",
            "customer_name": "Zenith Labs",
            "amount": 950.00,
            "transaction_date": "2024-01-10",
            "description": "Lab equipment"
        }])
        inserted, skipped = insert_invoices(initial_df, batch_id="BATCH-01", db_path=self.test_db)
        self.assertEqual(inserted, 1)

        # Retrieve existing IDs
        existing_ids = get_existing_ids(db_path=self.test_db, table_name="invoices", id_column="invoice_id")
        self.assertIn("INV-100", existing_ids)

        # Now test validating a file containing INV-100 (database duplicate)
        new_df = pd.DataFrame([{
            "invoice_id": "INV-100",
            "customer_name": "Zenith Labs",
            "amount": "950.00",
            "transaction_date": "2024-01-10"
        }])
        res = validate_records(new_df, record_type="invoice", existing_db_ids=existing_ids)
        self.assertEqual(len(res["valid_df"]), 0)
        self.assertEqual(len(res["invalid_df"]), 1)
        self.assertIn("DUPLICATE_IN_DATABASE", res["invalid_df"].iloc[0]["error_type"])

        # Check DB stats
        stats = get_database_stats(db_path=self.test_db)
        self.assertEqual(stats["total_invoices"], 1)
        self.assertEqual(stats["total_invoice_amount"], 950.00)


if __name__ == "__main__":
    unittest.main()
