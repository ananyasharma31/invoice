"""
Module 3: Match Review and Reconciliation Engine
Handles user review decisions (confirm, reject, manual allocation),
prevents double allocation of payments, protects against reintroducing rejected suggestions,
and calculates precise outstanding invoice balances using Python's Decimal.
"""

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set, Tuple
import pandas as pd


def to_decimal(val: Any) -> Decimal:
    """Safely converts any monetary value to a 2-decimal-place Decimal."""
    if val is None or pd.isna(val):
        return Decimal("0.00")
    try:
        # If float or int, convert via string to avoid float precision artifacts
        s = str(val).strip().replace("$", "").replace("₹", "").replace("€", "").replace("£", "").replace(",", "")
        d = Decimal(s)
        return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


class ReconciliationEngine:
    def __init__(self, db_manager=None):
        self.db = db_manager

    @staticmethod
    def calculate_invoice_balances(
        invoices_df: pd.DataFrame,
        confirmed_allocations_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculates confirmed paid amounts and outstanding invoice balances:
        Outstanding Balance = Invoice Amount - Confirmed Allocations
        
        Using Decimal for exact financial precision.
        """
        if invoices_df is None or invoices_df.empty:
            return pd.DataFrame(columns=[
                "invoice_id", "customer_name", "invoice_amount", "confirmed_paid",
                "outstanding_balance", "status", "reconciliation_pct"
            ])

        # Aggregate confirmed allocations per invoice
        allocations_by_inv: Dict[str, Decimal] = {}
        if confirmed_allocations_df is not None and not confirmed_allocations_df.empty:
            # Filter only CONFIRMED allocations
            confirmed_only = confirmed_allocations_df[
                confirmed_allocations_df["status"].str.upper() == "CONFIRMED"
            ]
            for _, row in confirmed_only.iterrows():
                inv_id = str(row.get("invoice_id", "")).strip().upper()
                amt = to_decimal(row.get("allocated_amount", 0.0))
                allocations_by_inv[inv_id] = allocations_by_inv.get(inv_id, Decimal("0.00")) + amt

        results = []
        for _, row in invoices_df.iterrows():
            inv_id = str(row.get("invoice_id", "")).strip().upper()
            cust_name = str(row.get("customer_name", ""))
            inv_amt = to_decimal(row.get("amount", 0.0))
            confirmed_paid = allocations_by_inv.get(inv_id, Decimal("0.00"))
            
            # Outstanding Balance = Invoice Amount - Confirmed Allocations
            outstanding = inv_amt - confirmed_paid

            if outstanding == Decimal("0.00") and inv_amt > Decimal("0.00"):
                status = "PAID"
            elif Decimal("0.00") < outstanding < inv_amt:
                status = "PARTIALLY PAID"
            elif outstanding == inv_amt:
                status = "UNPAID"
            elif outstanding < Decimal("0.00"):
                status = "OVERPAID"
            else:
                status = "PAID"

            pct_paid = float((confirmed_paid / inv_amt * 100)) if inv_amt > Decimal("0.00") else 100.0

            results.append({
                "invoice_id": inv_id,
                "customer_name": cust_name,
                "invoice_amount": float(inv_amt),
                "confirmed_paid": float(confirmed_paid),
                "outstanding_balance": float(outstanding),
                "status": status,
                "reconciliation_pct": round(min(100.0, max(0.0, pct_paid)), 1)
            })

        return pd.DataFrame(results)

    @staticmethod
    def calculate_payment_allocations(
        payments_df: pd.DataFrame,
        confirmed_allocations_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculates how much of each payment has been allocated,
        preventing double allocation and reporting remaining unallocated funds.
        """
        if payments_df is None or payments_df.empty:
            return pd.DataFrame(columns=[
                "payment_id", "customer_name", "payment_amount", "allocated_amount",
                "remaining_unallocated", "allocation_status"
            ])

        allocations_by_pmt: Dict[str, Decimal] = {}
        if confirmed_allocations_df is not None and not confirmed_allocations_df.empty:
            confirmed_only = confirmed_allocations_df[
                confirmed_allocations_df["status"].str.upper() == "CONFIRMED"
            ]
            for _, row in confirmed_only.iterrows():
                pmt_id = str(row.get("payment_id", "")).strip().upper()
                amt = to_decimal(row.get("allocated_amount", 0.0))
                allocations_by_pmt[pmt_id] = allocations_by_pmt.get(pmt_id, Decimal("0.00")) + amt

        results = []
        for _, row in payments_df.iterrows():
            pmt_id = str(row.get("payment_id", "")).strip().upper()
            cust_name = str(row.get("customer_name", ""))
            pmt_amt = to_decimal(row.get("amount", 0.0))
            allocated = allocations_by_pmt.get(pmt_id, Decimal("0.00"))
            remaining = pmt_amt - allocated

            if remaining <= Decimal("0.00"):
                alloc_status = "FULLY ALLOCATED"
            elif Decimal("0.00") < remaining < pmt_amt:
                alloc_status = "PARTIALLY ALLOCATED"
            else:
                alloc_status = "UNALLOCATED"

            results.append({
                "payment_id": pmt_id,
                "customer_name": cust_name,
                "payment_amount": float(pmt_amt),
                "allocated_amount": float(allocated),
                "remaining_unallocated": float(max(Decimal("0.00"), remaining)),
                "allocation_status": alloc_status
            })

        return pd.DataFrame(results)

    @staticmethod
    def validate_allocation(
        payment_id: str,
        invoice_id: str,
        amount_to_allocate: Decimal,
        payments_df: pd.DataFrame,
        invoices_df: pd.DataFrame,
        confirmed_allocations_df: Optional[pd.DataFrame] = None,
        rejected_pairs: Optional[Set[Tuple[str, str]]] = None
    ) -> Tuple[bool, str]:
        """
        Validates whether an allocation is legally allowed:
        1. Checks if pair was previously rejected by user.
        2. Prevents payment from being allocated more than its total amount (prevents double allocation).
        3. Prevents allocation amount from being <= 0.
        """
        p_id = payment_id.strip().upper()
        i_id = invoice_id.strip().upper()

        if amount_to_allocate <= Decimal("0.00"):
            return False, f"Allocation amount must be strictly positive (> 0), got: {amount_to_allocate}"

        # 1. Check if user previously rejected this match
        if rejected_pairs and (i_id, p_id) in rejected_pairs:
            return False, f"Match between Invoice '{i_id}' and Payment '{p_id}' was previously REJECTED by user. Un-reject it first before allocating."

        # Find payment row
        pmt_row = payments_df[payments_df["payment_id"].astype(str).str.strip().str.upper() == p_id]
        if pmt_row.empty:
            return False, f"Payment '{p_id}' not found in registered payment records."

        total_pmt_amt = to_decimal(pmt_row.iloc[0]["amount"])

        # Calculate already allocated amount for this payment
        already_allocated = Decimal("0.00")
        if confirmed_allocations_df is not None and not confirmed_allocations_df.empty:
            confirmed_records = confirmed_allocations_df[
                (confirmed_allocations_df["payment_id"].astype(str).str.strip().str.upper() == p_id) &
                (confirmed_allocations_df["status"].str.upper() == "CONFIRMED")
            ]
            for _, r in confirmed_records.iterrows():
                # If editing same invoice, allow replacement; otherwise count
                if str(r.get("invoice_id", "")).strip().upper() != i_id:
                    already_allocated += to_decimal(r.get("allocated_amount", 0.0))

        remaining_capacity = total_pmt_amt - already_allocated
        if amount_to_allocate > remaining_capacity:
            return False, (
                f"Double Allocation Error: Payment '{p_id}' total amount is ${total_pmt_amt:,.2f}. "
                f"${already_allocated:,.2f} is already confirmed for other invoices. "
                f"Maximum remaining allocatable amount is ${remaining_capacity:,.2f}, cannot allocate ${amount_to_allocate:,.2f}."
            )

        return True, "Valid allocation"

    @staticmethod
    def get_unresolved_transactions(
        invoices_summary_df: pd.DataFrame,
        payments_summary_df: pd.DataFrame
    ) -> Dict[str, pd.DataFrame]:
        """
        Returns unresolved transactions:
        - Unsettled Invoices (UNPAID or PARTIALLY PAID)
        - Unallocated Payments (UNALLOCATED or PARTIALLY ALLOCATED)
        """
        unsettled_invoices = invoices_summary_df[
            invoices_summary_df["status"].isin(["UNPAID", "PARTIALLY PAID", "OVERPAID"])
        ].copy() if invoices_summary_df is not None and not invoices_summary_df.empty else pd.DataFrame()

        unallocated_payments = payments_summary_df[
            payments_summary_df["allocation_status"].isin(["UNALLOCATED", "PARTIALLY ALLOCATED"])
        ].copy() if payments_summary_df is not None and not payments_summary_df.empty else pd.DataFrame()

        return {
            "unsettled_invoices": unsettled_invoices,
            "unallocated_payments": unallocated_payments
        }
