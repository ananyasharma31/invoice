"""
Unit and Integration Tests for Module 3: Match Review and Reconciliation
Verifies:
- Decimal calculation of outstanding invoice balances (Formula: Outstanding = Amount - Confirmed Paid)
- Exact prompt examples (INV-101 -> 0, INV-102 -> 1,000, INV-103 -> 7,000)
- Prevention of double-allocation for payments
- Preservation of user rejections (preventing rejected matches from being reintroduced)
- SQLite persistence of user confirmation and rejection decisions
"""

import os
import unittest
from decimal import Decimal
import pandas as pd

from reconciliation import to_decimal, ReconciliationEngine
from database import (
    init_db,
    record_allocation,
    get_allocations,
    get_rejected_pairs,
    reset_database
)
from matcher import IntelligentTransactionMatcher


class TestReconciliationModule(unittest.TestCase):
    def setUp(self):
        self.test_db = os.path.join(os.path.dirname(__file__), "test_reconciliation_m3.db")
        reset_database(self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                reset_database(self.test_db)
            except Exception:
                pass

    def test_decimal_outstanding_balance_calculation(self):
        # Prompt Example:
        # INV-101 | ₹5,000 | Confirmed Paid: ₹5,000 | Outstanding: ₹0
        # INV-102 | ₹3,000 | Confirmed Paid: ₹2,000 | Outstanding: ₹1,000
        # INV-103 | ₹7,000 | Confirmed Paid: ₹0     | Outstanding: ₹7,000

        invoices_df = pd.DataFrame([
            {"invoice_id": "INV-101", "customer_name": "Acme Corp", "amount": 5000.00},
            {"invoice_id": "INV-102", "customer_name": "Global Logistics", "amount": 3000.00},
            {"invoice_id": "INV-103", "customer_name": "Apex Innovations", "amount": 7000.00}
        ])

        confirmed_allocations_df = pd.DataFrame([
            {"invoice_id": "INV-101", "payment_id": "PAY-201", "allocated_amount": 5000.00, "status": "CONFIRMED"},
            {"invoice_id": "INV-102", "payment_id": "PAY-202", "allocated_amount": 2000.00, "status": "CONFIRMED"}
            # INV-103 has no allocations
        ])

        balances_df = ReconciliationEngine.calculate_invoice_balances(invoices_df, confirmed_allocations_df)

        # Check INV-101: Outstanding = 0.00, Status = PAID
        inv101 = balances_df[balances_df["invoice_id"] == "INV-101"].iloc[0]
        self.assertEqual(inv101["invoice_amount"], 5000.00)
        self.assertEqual(inv101["confirmed_paid"], 5000.00)
        self.assertEqual(inv101["outstanding_balance"], 0.00)
        self.assertEqual(inv101["status"], "PAID")

        # Check INV-102: Outstanding = 1000.00, Status = PARTIALLY PAID
        inv102 = balances_df[balances_df["invoice_id"] == "INV-102"].iloc[0]
        self.assertEqual(inv102["invoice_amount"], 3000.00)
        self.assertEqual(inv102["confirmed_paid"], 2000.00)
        self.assertEqual(inv102["outstanding_balance"], 1000.00)
        self.assertEqual(inv102["status"], "PARTIALLY PAID")

        # Check INV-103: Outstanding = 7000.00, Status = UNPAID
        inv103 = balances_df[balances_df["invoice_id"] == "INV-103"].iloc[0]
        self.assertEqual(inv103["invoice_amount"], 7000.00)
        self.assertEqual(inv103["confirmed_paid"], 0.00)
        self.assertEqual(inv103["outstanding_balance"], 7000.00)
        self.assertEqual(inv103["status"], "UNPAID")

    def test_prevent_double_allocation_of_payment(self):
        payments_df = pd.DataFrame([
            {"payment_id": "PAY-201", "amount": 5000.00}
        ])
        invoices_df = pd.DataFrame([
            {"invoice_id": "INV-101", "amount": 5000.00},
            {"invoice_id": "INV-999", "amount": 5000.00}
        ])

        # Allocate full 5,000 of PAY-201 to INV-101
        existing_allocations = pd.DataFrame([
            {"invoice_id": "INV-101", "payment_id": "PAY-201", "allocated_amount": 5000.00, "status": "CONFIRMED"}
        ])

        # Attempt to allocate another 1,000 of the same PAY-201 to INV-999 -> Must be rejected!
        valid, msg = ReconciliationEngine.validate_allocation(
            payment_id="PAY-201",
            invoice_id="INV-999",
            amount_to_allocate=Decimal("1000.00"),
            payments_df=payments_df,
            invoices_df=invoices_df,
            confirmed_allocations_df=existing_allocations
        )
        self.assertFalse(valid)
        self.assertIn("Double Allocation Error", msg)

    def test_preserve_user_rejections_and_prevent_reintroduction(self):
        # User rejects match between INV-101 and PAY-201
        record_allocation(
            invoice_id="INV-101",
            payment_id="PAY-201",
            allocated_amount=0.0,
            status="REJECTED",
            user_notes="Wrong client account",
            db_path=self.test_db
        )

        rejected = get_rejected_pairs(db_path=self.test_db)
        self.assertIn(("INV-101", "PAY-201"), rejected)

        # Ensure matcher does NOT reintroduce this match
        inv_df = pd.DataFrame([
            {"invoice_id": "INV-101", "customer_name": "Acme Corp", "amount": 5000.00, "transaction_date": "2024-01-10"}
        ])
        pmt_df = pd.DataFrame([
            {"payment_id": "PAY-201", "invoice_id": "INV-101", "customer_name": "Acme Corp", "amount": 5000.00, "transaction_date": "2024-01-14"}
        ])

        matcher = IntelligentTransactionMatcher()
        match_result = matcher.match_transactions(inv_df, pmt_df, rejected_pairs=rejected)

        # The rejected pair must NOT be suggested
        self.assertEqual(len(match_result["matches_df"]), 0)
        self.assertEqual(len(match_result["unmatched_payments_df"]), 1)

    def test_unresolved_transactions_breakdown(self):
        invoices_summary = pd.DataFrame([
            {"invoice_id": "INV-101", "status": "PAID", "outstanding_balance": 0.0},
            {"invoice_id": "INV-102", "status": "PARTIALLY PAID", "outstanding_balance": 1000.0},
            {"invoice_id": "INV-103", "status": "UNPAID", "outstanding_balance": 7000.0}
        ])
        payments_summary = pd.DataFrame([
            {"payment_id": "PAY-201", "allocation_status": "FULLY ALLOCATED", "remaining_unallocated": 0.0},
            {"payment_id": "PAY-202", "allocation_status": "PARTIALLY ALLOCATED", "remaining_unallocated": 1000.0},
            {"payment_id": "PAY-203", "allocation_status": "UNALLOCATED", "remaining_unallocated": 6500.0}
        ])

        unresolved = ReconciliationEngine.get_unresolved_transactions(invoices_summary, payments_summary)
        # Should have 2 unsettled invoices (INV-102, INV-103)
        self.assertEqual(len(unresolved["unsettled_invoices"]), 2)
        # Should have 2 unallocated payments (PAY-202, PAY-203)
        self.assertEqual(len(unresolved["unallocated_payments"]), 2)


if __name__ == "__main__":
    unittest.main()
