"""
Module 2: Intelligent Transaction Matching Engine
Uses RapidFuzz, amount comparison, date plausibility analysis, and reference parsing
to automatically match payments with invoices, assign confidence scores, generate
transparent explanations, and flag ambiguous cases for manual review.
"""

import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
import pandas as pd
from rapidfuzz import fuzz


class IntelligentTransactionMatcher:
    def __init__(
        self,
        customer_name_threshold: float = 70.0,
        amount_tolerance_percent: float = 0.0,
        max_date_gap_days: int = 90
    ):
        """
        Initializes the matcher with configurable thresholds.
        :param customer_name_threshold: Minimum RapidFuzz token_sort_ratio to consider names related.
        :param amount_tolerance_percent: Percentage tolerance for amount rounding or small fees (default 0.0 for exact).
        :param max_date_gap_days: Maximum plausible days between invoice date and payment date.
        """
        self.customer_name_threshold = customer_name_threshold
        self.amount_tolerance_percent = amount_tolerance_percent
        self.max_date_gap_days = max_date_gap_days

    @staticmethod
    def clean_text_for_comparison(text: Any) -> str:
        """Cleans and standardizes text for fuzzy matching by removing common legal suffixes."""
        if text is None or pd.isna(text):
            return ""
        s = str(text).lower().strip()
        # Remove common corporate suffixes for sharper fuzzy comparison
        s = re.sub(r"\b(inc|incorporated|corp|corporation|llc|ltd|limited|pvt|co|company)\b", "", s)
        s = re.sub(r"[^\w\s]", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    @staticmethod
    def parse_iso_date(date_str: Any) -> Optional[datetime]:
        """Parses standardized YYYY-MM-DD date."""
        if not date_str or pd.isna(date_str):
            return None
        try:
            return datetime.strptime(str(date_str).strip()[:10], "%Y-%m-%d")
        except Exception:
            return None

    @staticmethod
    def extract_invoice_references_from_text(text: Any) -> List[str]:
        """Extracts potential invoice IDs (e.g., INV-2024-001, INV101, #1002) from descriptions."""
        if not text or pd.isna(text):
            return []
        matches = re.findall(r"\b(?:INV|BILL|REC)[-_]?\d{3,8}\b", str(text).upper())
        return matches

    def calculate_match_score(
        self,
        invoice_row: Dict[str, Any],
        payment_row: Dict[str, Any]
    ) -> Tuple[float, str, str, List[str], Dict[str, Any]]:
        """
        Calculates match score (0 to 100), confidence level, evidence explanation,
        and review flags between an invoice and a payment.
        
        Returns:
            (score, confidence_level, evidence_str, flags_list, details_dict)
        """
        score = 0.0
        evidence_points = []
        flags = []
        details = {}

        # ----------------------------------------------------------------------
        # 1. Invoice Reference Comparison (Up to 40 Points)
        # ----------------------------------------------------------------------
        inv_id_clean = str(invoice_row.get("invoice_id", "")).strip().upper()
        pmt_inv_ref = str(payment_row.get("invoice_id", "")).strip().upper()
        pmt_desc = str(payment_row.get("description", ""))

        extracted_refs = self.extract_invoice_references_from_text(pmt_desc)

        ref_matched = False
        if pmt_inv_ref and pmt_inv_ref != "NONE" and pmt_inv_ref == inv_id_clean:
            score += 40.0
            ref_matched = True
            evidence_points.append("Exact invoice reference")
            details["reference_match"] = "Exact"
        elif inv_id_clean in extracted_refs:
            score += 35.0
            ref_matched = True
            evidence_points.append(f"Invoice reference '{inv_id_clean}' found in payment description")
            details["reference_match"] = "Extracted from memo"
        elif pmt_inv_ref and fuzz.ratio(pmt_inv_ref, inv_id_clean) > 85:
            score += 25.0
            ref_matched = True
            evidence_points.append(f"Near-match invoice reference ('{pmt_inv_ref}' vs '{inv_id_clean}')")
            details["reference_match"] = "Near-match"
            flags.append("FUZZY_REFERENCE_MATCH")
        else:
            details["reference_match"] = "No reference"

        # ----------------------------------------------------------------------
        # 2. Customer Name Similarity using RapidFuzz (Up to 30 Points)
        # ----------------------------------------------------------------------
        inv_cust = str(invoice_row.get("customer_name", ""))
        pmt_cust = str(payment_row.get("customer_name", ""))
        
        clean_inv_cust = self.clean_text_for_comparison(inv_cust)
        clean_pmt_cust = self.clean_text_for_comparison(pmt_cust)

        # RapidFuzz token_sort_ratio handles word reordering well (e.g. "Acme Corp" vs "Corp, Acme")
        name_sim = fuzz.token_sort_ratio(clean_inv_cust, clean_pmt_cust)
        details["customer_similarity_pct"] = round(name_sim, 1)

        if name_sim >= 98:
            score += 30.0
            evidence_points.append("Matching customer name")
            details["customer_match"] = "Exact"
        elif name_sim >= self.customer_name_threshold:
            # Scaled score from 15 to 28
            scaled_name_score = 15.0 + ((name_sim - self.customer_name_threshold) / (100.0 - self.customer_name_threshold)) * 13.0
            score += scaled_name_score
            evidence_points.append(f"Similar customer name (RapidFuzz: {name_sim:.0f}%)")
            details["customer_match"] = f"Fuzzy ({name_sim:.0f}%)"
            flags.append("FUZZY_NAME_MATCH")
        else:
            details["customer_match"] = f"Low similarity ({name_sim:.0f}%)"
            if not ref_matched:
                flags.append("CUSTOMER_MISMATCH")

        # ----------------------------------------------------------------------
        # 3. Amount Comparison (Up to 20 Points)
        # ----------------------------------------------------------------------
        try:
            inv_amt = float(invoice_row.get("amount", 0.0))
            pmt_amt = float(payment_row.get("amount", 0.0))
        except (ValueError, TypeError):
            inv_amt = 0.0
            pmt_amt = 0.0

        amt_diff = round(pmt_amt - inv_amt, 2)
        details["invoice_amount"] = inv_amt
        details["payment_amount"] = pmt_amt
        details["amount_diff"] = amt_diff

        if inv_amt > 0 and abs(amt_diff) < 0.01:
            score += 20.0
            evidence_points.append("Matching amount")
            details["amount_status"] = "Exact Match"
        elif inv_amt > 0:
            diff_pct = (abs(amt_diff) / inv_amt) * 100.0
            if diff_pct <= max(1.0, self.amount_tolerance_percent):
                score += 12.0
                evidence_points.append(f"Amount within minor tolerance ({diff_pct:.1f}% diff)")
                details["amount_status"] = f"Minor Diff (${amt_diff:+.2f})"
                flags.append("MINOR_AMOUNT_DIFF")
            else:
                details["amount_status"] = f"Discrepancy (${amt_diff:+.2f})"
                flags.append("AMOUNT_MISMATCH")
                flags.append("REVIEW_REQUIRED")
                if amt_diff < 0:
                    evidence_points.append(f"Partial amount discrepancy (Diff: ${amt_diff:,.2f})")
                else:
                    evidence_points.append(f"Overpayment discrepancy (Diff: +${amt_diff:,.2f})")

        # ----------------------------------------------------------------------
        # 4. Transaction Date Analysis & Plausibility (Up to 10 Points)
        # ----------------------------------------------------------------------
        inv_dt = self.parse_iso_date(invoice_row.get("transaction_date"))
        pmt_dt = self.parse_iso_date(payment_row.get("transaction_date"))

        if inv_dt and pmt_dt:
            delta_days = (pmt_dt - inv_dt).days
            details["date_gap_days"] = delta_days

            if 0 <= delta_days <= 14:
                score += 10.0
                evidence_points.append(f"Payment settled promptly ({delta_days} days after invoice)")
                details["date_plausibility"] = "Prompt Settlement"
            elif 15 <= delta_days <= self.max_date_gap_days:
                score += 7.0
                evidence_points.append(f"Payment made {delta_days} days after invoice")
                details["date_plausibility"] = "Plausible Window"
            elif delta_days > self.max_date_gap_days:
                score += 2.0
                evidence_points.append(f"Payment delayed by {delta_days} days")
                details["date_plausibility"] = "Late Payment"
                flags.append("LATE_PAYMENT")
            else:
                # Payment predates invoice
                if abs(delta_days) <= 3:
                    score += 5.0
                    details["date_plausibility"] = "Same-period/Pre-payment"
                else:
                    details["date_plausibility"] = f"Payment predates invoice by {abs(delta_days)} days"
                    flags.append("DATE_ANOMALY")
                    flags.append("REVIEW_REQUIRED")
                    evidence_points.append(f"Payment predates invoice by {abs(delta_days)} days")
        else:
            details["date_plausibility"] = "Date Missing/Unparsed"

        # ----------------------------------------------------------------------
        # 5. Synthesize Confidence Level and Evidence
        # ----------------------------------------------------------------------
        final_score = min(100.0, max(0.0, round(score, 1)))

        # Categorize confidence level
        if "AMOUNT_MISMATCH" in flags or "DATE_ANOMALY" in flags or "CUSTOMER_MISMATCH" in flags:
            confidence_level = "Review required"
            if "REVIEW_REQUIRED" not in flags:
                flags.append("REVIEW_REQUIRED")
        elif final_score >= 80.0 and ref_matched and abs(amt_diff) < 0.01:
            confidence_level = "High"
        elif final_score >= 55.0 and abs(amt_diff) < 0.01:
            confidence_level = "Medium"
        elif final_score >= 45.0:
            confidence_level = "Review required"
            flags.append("REVIEW_REQUIRED")
        else:
            confidence_level = "Review required"
            flags.append("REVIEW_REQUIRED")

        # Format natural language evidence summary matching prompt example
        if ref_matched and abs(amt_diff) < 0.01:
            evidence_summary = "Exact invoice reference and amount"
        elif name_sim >= self.customer_name_threshold and abs(amt_diff) < 0.01:
            evidence_summary = f"Similar customer name and matching amount ({name_sim:.0f}% similarity)"
        elif name_sim >= self.customer_name_threshold and abs(amt_diff) >= 0.01:
            evidence_summary = f"Customer matches, but amount differs (Diff: ${amt_diff:+,.2f})"
        else:
            evidence_summary = "; ".join(evidence_points) if evidence_points else "Partial heuristic correlation"

        return final_score, confidence_level, evidence_summary, list(set(flags)), details

    def match_transactions(
        self,
        invoices_df: pd.DataFrame,
        payments_df: pd.DataFrame,
        rejected_pairs: Optional[Set[Tuple[str, str]]] = None,
        fully_allocated_payment_ids: Optional[Set[str]] = None
    ) -> Dict[str, Any]:
        """
        Executes intelligent matching between sets of invoices and payments.
        Preserves user corrections: filters out rejected pairs and fully allocated payments.
        
        Returns dictionary with:
        - matches_df: DataFrame of suggested matches with confidence, evidence, and review flags
        - unmatched_invoices_df: Invoices with no suitable payment candidate
        - unmatched_payments_df: Payments with no suitable invoice candidate
        - summary_metrics: Counts of High, Medium, Review Required, and match rates
        """
        if rejected_pairs is None:
            rejected_pairs = set()
        if fully_allocated_payment_ids is None:
            fully_allocated_payment_ids = set()

        if invoices_df is None or invoices_df.empty or payments_df is None or payments_df.empty:
            return {
                "matches_df": pd.DataFrame(),
                "unmatched_invoices_df": invoices_df.copy() if invoices_df is not None else pd.DataFrame(),
                "unmatched_payments_df": payments_df.copy() if payments_df is not None else pd.DataFrame(),
                "summary_metrics": {
                    "total_invoices": len(invoices_df) if invoices_df is not None else 0,
                    "total_payments": len(payments_df) if payments_df is not None else 0,
                    "total_matches": 0,
                    "high_confidence_count": 0,
                    "medium_confidence_count": 0,
                    "review_required_count": 0,
                    "unmatched_payments_count": len(payments_df) if payments_df is not None else 0,
                    "unmatched_invoices_count": len(invoices_df) if invoices_df is not None else 0
                }
            }

        # Candidate matrix: evaluate all payments against potential invoices
        match_candidates: List[Dict[str, Any]] = []

        for p_idx, p_row in payments_df.iterrows():
            p_dict = p_row.to_dict()
            pmt_id = str(p_dict.get("payment_id", f"PAY-{p_idx+1}")).strip().upper()
            
            # Skip payments that have already been 100% allocated by the user
            if pmt_id in fully_allocated_payment_ids:
                continue

            candidates_for_this_payment = []

            for i_idx, i_row in invoices_df.iterrows():
                i_dict = i_row.to_dict()
                inv_id = str(i_dict.get("invoice_id", f"INV-{i_idx+1}")).strip().upper()

                # User correction preservation: skip pairs previously rejected by the user
                if (inv_id, pmt_id) in rejected_pairs:
                    continue

                score, confidence_level, evidence, flags, details = self.calculate_match_score(
                    invoice_row=i_dict,
                    payment_row=p_dict
                )

                # Keep candidate if score has reasonable correlation (> 30)
                if score >= 30.0:
                    candidates_for_this_payment.append({
                        "payment_id": pmt_id,
                        "invoice_id": inv_id,
                        "confidence_score": score,
                        "confidence": confidence_level,
                        "matching_evidence": evidence,
                        "review_flags": ", ".join(flags) if flags else "CLEAN_MATCH",
                        "invoice_amount": details.get("invoice_amount", 0.0),
                        "payment_amount": details.get("payment_amount", 0.0),
                        "amount_diff": details.get("amount_diff", 0.0),
                        "customer_similarity": details.get("customer_similarity_pct", 0.0),
                        "date_gap_days": details.get("date_gap_days", 0),
                        "invoice_customer": str(i_dict.get("customer_name", "")),
                        "payment_customer": str(p_dict.get("customer_name", "")),
                        "invoice_date": str(i_dict.get("transaction_date", "")),
                        "payment_date": str(p_dict.get("transaction_date", ""))
                    })

            # Check for ambiguity: if multiple candidates have very close high scores
            if len(candidates_for_this_payment) > 1:
                candidates_for_this_payment.sort(key=lambda x: x["confidence_score"], reverse=True)
                top_cand = candidates_for_this_payment[0]
                second_cand = candidates_for_this_payment[1]
                
                # If top two candidates are within 5 points of each other
                if (top_cand["confidence_score"] - second_cand["confidence_score"]) < 5.0 and top_cand["confidence_score"] > 60:
                    top_cand["review_flags"] += ", AMBIGUOUS_CANDIDATES"
                    top_cand["confidence"] = "Review required"
                    top_cand["matching_evidence"] += f" (Note: Ambiguous match with {second_cand['invoice_id']})"
                
                match_candidates.append(top_cand)
            elif len(candidates_for_this_payment) == 1:
                match_candidates.append(candidates_for_this_payment[0])

        # Resolve 1-to-1 matches: If multiple payments claimed the same invoice, rank by score
        final_matches: List[Dict[str, Any]] = []
        assigned_invoices = set()
        assigned_payments = set()

        # Sort all candidates by score descending
        match_candidates.sort(key=lambda x: x["confidence_score"], reverse=True)

        for cand in match_candidates:
            p_id = cand["payment_id"]
            i_id = cand["invoice_id"]

            if p_id in assigned_payments:
                continue

            if i_id in assigned_invoices:
                # Invoice already claimed by a higher-scoring payment -> flag as shared/ambiguous
                cand["review_flags"] += ", INVOICE_ALREADY_MATCHED"
                cand["confidence"] = "Review required"
                cand["matching_evidence"] += " (Multiple payments candidate for same invoice)"

            assigned_invoices.add(i_id)
            assigned_payments.add(p_id)
            final_matches.append(cand)

        matches_df = pd.DataFrame(final_matches) if final_matches else pd.DataFrame(
            columns=["invoice_id", "payment_id", "matching_evidence", "confidence", "confidence_score", "review_flags"]
        )

        # Determine unmatched records
        matched_inv_ids = set(matches_df["invoice_id"].unique()) if not matches_df.empty else set()
        matched_pmt_ids = set(matches_df["payment_id"].unique()) if not matches_df.empty else set()

        unmatched_invoices_df = invoices_df[~invoices_df["invoice_id"].astype(str).isin(matched_inv_ids)].copy()
        unmatched_payments_df = payments_df[~payments_df["payment_id"].astype(str).isin(matched_pmt_ids)].copy()

        # Summary statistics
        high_cnt = int((matches_df["confidence"] == "High").sum()) if not matches_df.empty else 0
        med_cnt = int((matches_df["confidence"] == "Medium").sum()) if not matches_df.empty else 0
        rev_cnt = int((matches_df["confidence"] == "Review required").sum()) if not matches_df.empty else 0

        summary = {
            "total_invoices": len(invoices_df),
            "total_payments": len(payments_df),
            "total_matches": len(matches_df),
            "high_confidence_count": high_cnt,
            "medium_confidence_count": med_cnt,
            "review_required_count": rev_cnt,
            "unmatched_payments_count": len(unmatched_payments_df),
            "unmatched_invoices_count": len(unmatched_invoices_df)
        }

        return {
            "matches_df": matches_df,
            "unmatched_invoices_df": unmatched_invoices_df,
            "unmatched_payments_df": unmatched_payments_df,
            "summary_metrics": summary
        }
