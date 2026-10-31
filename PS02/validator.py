"""
Data Validation and Normalization Engine
Validates invoice and payment records, normalizes fields (names, dates, descriptions),
detects missing fields, invalid amounts, and duplicates (both in-file and database).
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional, Set
import pandas as pd
from dateutil import parser as date_parser


# Common alias mappings for auto-detecting columns in uploaded CSVs
INVOICE_COLUMN_ALIASES = {
    "invoice_id": ["invoice_id", "invoice_number", "invoiceno", "inv_id", "id", "bill_no", "bill_id", "invoice #"],
    "customer_name": ["customer_name", "customer", "client_name", "client", "buyer_name", "buyer", "company_name"],
    "amount": ["amount", "total_amount", "invoice_amount", "total", "net_amount", "inv_amount", "price"],
    "transaction_date": ["transaction_date", "invoice_date", "date", "txn_date", "inv_date", "issue_date", "created_date"],
    "description": ["description", "desc", "memo", "notes", "particulars", "line_item", "details"]
}

PAYMENT_COLUMN_ALIASES = {
    "payment_id": ["payment_id", "transaction_id", "txn_id", "payment_no", "pay_id", "receipt_id", "ref_id", "payment #"],
    "invoice_id": ["invoice_id", "invoice_number", "invoiceno", "inv_id", "bill_id", "bill_no", "invoice_ref", "ref_invoice"],
    "customer_name": ["customer_name", "customer", "client_name", "client", "payer_name", "payer", "company_name"],
    "amount": ["amount", "payment_amount", "paid_amount", "total", "txn_amount", "paid"],
    "transaction_date": ["transaction_date", "payment_date", "date", "txn_date", "pay_date", "deposit_date", "settlement_date"],
    "description": ["description", "desc", "memo", "notes", "remarks", "payment_details"],
    "payment_method": ["payment_method", "method", "mode", "payment_mode", "channel", "type", "pay_type"]
}


def map_columns(df: pd.DataFrame, aliases: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Attempts to match DataFrame columns to canonical schema names using alias lookup.
    Returns mapping: {canonical_col: matched_df_col}.
    """
    mapping = {}
    df_cols = {str(col).strip().lower(): col for col in df.columns}

    for canonical, alias_list in aliases.items():
        for alias in alias_list:
            alias_clean = alias.strip().lower()
            if alias_clean in df_cols:
                mapping[canonical] = df_cols[alias_clean]
                break

    return mapping


def normalize_customer_name(name: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalizes customer names:
    - Strips whitespace
    - Replaces internal multiple spaces/tabs
    - Trims trailing punctuation (, . - /)
    - Applies standard Title Case
    Returns (normalized_name, error_message).
    """
    if pd.isna(name) or name is None:
        return None, "Customer name is missing or empty"

    name_str = str(name).strip()
    if not name_str or name_str.lower() in {"nan", "none", "null", "n/a", ""}:
        return None, "Customer name is blank"

    # Remove repeated whitespace
    cleaned = re.sub(r"\s+", " ", name_str)
    # Remove leading/trailing unwanted punctuation but keep apostrophes/periods in initials
    cleaned = re.sub(r"^[,\.\-\/\s]+|[,\-\/\s]+$", "", cleaned)

    if len(cleaned) < 2:
        return None, f"Customer name '{name_str}' is too short or invalid"

    # Title-case for consistency
    normalized = cleaned.title()
    return normalized, None


def normalize_date(date_val: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Normalizes transaction dates to standardized ISO format 'YYYY-MM-DD'.
    Handles multiple international date formats (YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, etc.).
    Returns (normalized_date_str, error_message).
    """
    if pd.isna(date_val) or date_val is None:
        return None, "Transaction date is missing"

    date_str = str(date_val).strip()
    if not date_str or date_str.lower() in {"nan", "none", "null", "n/a", ""}:
        return None, "Transaction date is empty"

    try:
        # Use python-dateutil parser with dayfirst heuristic support
        # If string contains dashes or slashes, try intelligent parse
        parsed_dt = date_parser.parse(date_str, fuzzy=False)
        
        # Sanity check year range
        if parsed_dt.year < 1990 or parsed_dt.year > 2050:
            return None, f"Date '{date_str}' has unrealistic year: {parsed_dt.year}"

        normalized = parsed_dt.strftime("%Y-%m-%d")
        return normalized, None
    except Exception as exc:
        return None, f"Unable to parse date '{date_str}': {str(exc)}"


def normalize_amount(amount_val: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Validates and normalizes monetary amount:
    - Strips currency signs ($, €, £, ₹, ¥) and thousands separators (,)
    - Parses to positive float
    Returns (normalized_amount, error_message).
    """
    if pd.isna(amount_val) or amount_val is None:
        return None, "Amount is missing"

    amt_str = str(amount_val).strip()
    if not amt_str or amt_str.lower() in {"nan", "none", "null", "n/a", ""}:
        return None, "Amount is blank"

    # Remove currency symbols and comma separators
    cleaned_amt = re.sub(r"[$\€\£\₹\¥\s\,]", "", amt_str)

    try:
        parsed_amt = float(cleaned_amt)
    except ValueError:
        return None, f"Amount '{amt_str}' is not a valid numeric value"

    if parsed_amt <= 0:
        return None, f"Amount must be strictly positive (> 0), got: {parsed_amt}"

    # Round to 2 decimal places for financial accuracy
    return round(parsed_amt, 2), None


def normalize_description(desc: Any, default: str = "Standard Transaction") -> str:
    """
    Normalizes transaction descriptions:
    - Strips whitespace
    - Normalizes internal multiple spaces
    - Capitalizes first character
    """
    if pd.isna(desc) or desc is None:
        return default

    desc_str = str(desc).strip()
    if not desc_str or desc_str.lower() in {"nan", "none", "null", "n/a", ""}:
        return default

    cleaned = re.sub(r"\s+", " ", desc_str)
    return cleaned[0].upper() + cleaned[1:] if cleaned else default


def validate_records(
    df: pd.DataFrame,
    record_type: str = "invoice",  # 'invoice' or 'payment'
    existing_db_ids: Optional[Set[str]] = None,
    column_mapping: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Comprehensive validator for invoices and payments.
    
    Identifies:
    - Missing required fields
    - Invalid amounts (negative, zero, non-numeric)
    - Unparseable dates
    - Duplicate records within CSV file
    - Duplicate records already present in SQLite database
    
    Normalizes:
    - Customer names, transaction dates, and descriptions
    
    Returns a dictionary containing:
    - valid_df: pd.DataFrame of clean records
    - invalid_df: pd.DataFrame of rejected records with reason and error category
    - metrics: dictionary of breakdown stats
    """
    if existing_db_ids is None:
        existing_db_ids = set()

    aliases = INVOICE_COLUMN_ALIASES if record_type == "invoice" else PAYMENT_COLUMN_ALIASES
    mapped_cols = column_mapping if column_mapping else map_columns(df, aliases)

    required_canonical_cols = ["invoice_id", "customer_name", "amount", "transaction_date"]
    if record_type == "payment":
        required_canonical_cols = ["payment_id", "customer_name", "amount", "transaction_date"]

    # Check for missing required columns in file header
    missing_header_cols = [col for col in required_canonical_cols if col not in mapped_cols]
    if missing_header_cols:
        return {
            "valid_df": pd.DataFrame(),
            "invalid_df": pd.DataFrame([{
                "row_index": 0,
                "record_id": "HEADER_ERROR",
                "error_type": "MISSING_COLUMN_HEADER",
                "problematic_field": ", ".join(missing_header_cols),
                "error_details": f"Required column(s) not found in CSV: {missing_header_cols}. Available columns: {list(df.columns)}"
            }]),
            "metrics": {
                "total_rows": len(df),
                "valid_count": 0,
                "invalid_count": len(df),
                "file_duplicate_count": 0,
                "db_duplicate_count": 0,
                "header_error": True
            }
        }

    id_canonical_key = "invoice_id" if record_type == "invoice" else "payment_id"
    id_col_source = mapped_cols[id_canonical_key]

    valid_records: List[Dict[str, Any]] = []
    invalid_records: List[Dict[str, Any]] = []

    seen_file_ids: Set[str] = set()
    file_duplicates_count = 0
    db_duplicates_count = 0

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-indexed including header row
        row_dict = row.to_dict()
        raw_id_val = row_dict.get(id_col_source)
        
        errors: List[str] = []
        error_types: List[str] = []
        error_fields: List[str] = []

        # 1. Primary ID Check
        if pd.isna(raw_id_val) or not str(raw_id_val).strip() or str(raw_id_val).strip().lower() in {"nan", "none", "null"}:
            errors.append(f"{id_canonical_key.replace('_', ' ').title()} is missing or empty")
            error_types.append("MISSING_FIELD")
            error_fields.append(id_canonical_key)
            rec_id = f"ROW_{row_num}"
        else:
            rec_id = str(raw_id_val).strip().upper()

            # Check duplicate in current file
            if rec_id in seen_file_ids:
                errors.append(f"Duplicate {id_canonical_key} '{rec_id}' found within this upload file")
                error_types.append("DUPLICATE_IN_FILE")
                error_fields.append(id_canonical_key)
                file_duplicates_count += 1
            else:
                seen_file_ids.add(rec_id)

            # Check duplicate in SQLite database
            if rec_id in existing_db_ids:
                errors.append(f"{id_canonical_key.replace('_', ' ').title()} '{rec_id}' already exists in SQLite database")
                error_types.append("DUPLICATE_IN_DATABASE")
                error_fields.append(id_canonical_key)
                db_duplicates_count += 1

        # 2. For payment, check reference invoice_id (optional reference, can be empty for unmatched payments)
        ref_invoice_id = ""
        if record_type == "payment":
            inv_col = mapped_cols.get("invoice_id")
            raw_inv_ref = row_dict.get(inv_col) if inv_col else None
            if not pd.isna(raw_inv_ref) and str(raw_inv_ref).strip() and str(raw_inv_ref).strip().lower() not in {"nan", "none", "null"}:
                ref_invoice_id = str(raw_inv_ref).strip().upper()
            else:
                ref_invoice_id = ""  # Left unassigned for Module 2 intelligent matching!

        # 3. Customer Name Normalization & Validation
        cust_col = mapped_cols.get("customer_name")
        norm_name, name_err = normalize_customer_name(row_dict.get(cust_col))
        if name_err:
            errors.append(name_err)
            error_types.append("MISSING_FIELD" if "missing" in name_err.lower() or "blank" in name_err.lower() else "INVALID_NAME")
            error_fields.append("customer_name")

        # 4. Amount Normalization & Validation
        amt_col = mapped_cols.get("amount")
        norm_amt, amt_err = normalize_amount(row_dict.get(amt_col))
        if amt_err:
            errors.append(amt_err)
            error_types.append("INVALID_AMOUNT")
            error_fields.append("amount")

        # 5. Date Normalization & Validation
        date_col = mapped_cols.get("transaction_date")
        norm_date, date_err = normalize_date(row_dict.get(date_col))
        if date_err:
            errors.append(date_err)
            error_types.append("INVALID_DATE")
            error_fields.append("transaction_date")

        # 6. Description Normalization
        desc_col = mapped_cols.get("description")
        default_desc = "Standard Invoice Item" if record_type == "invoice" else "Payment Settlement"
        norm_desc = normalize_description(row_dict.get(desc_col) if desc_col else None, default=default_desc)

        # 7. Payment method (if payment)
        norm_method = "Bank Transfer"
        if record_type == "payment":
            method_col = mapped_cols.get("payment_method")
            if method_col and not pd.isna(row_dict.get(method_col)):
                norm_method = str(row_dict.get(method_col)).strip().title()

        # Decision: Valid or Invalid
        if errors:
            invalid_records.append({
                "row_number": row_num,
                "record_id": rec_id,
                "error_type": " & ".join(set(error_types)),
                "problematic_field": ", ".join(set(error_fields)),
                "error_details": "; ".join(errors),
                "raw_data": row_dict
            })
        else:
            clean_record = {
                "customer_name": norm_name,
                "amount": norm_amt,
                "transaction_date": norm_date,
                "description": norm_desc
            }
            if record_type == "invoice":
                clean_record["invoice_id"] = rec_id
            else:
                clean_record["payment_id"] = rec_id
                clean_record["invoice_id"] = ref_invoice_id
                clean_record["payment_method"] = norm_method

            valid_records.append(clean_record)

    valid_df = pd.DataFrame(valid_records) if valid_records else pd.DataFrame(columns=required_canonical_cols)
    invalid_df = pd.DataFrame(invalid_records) if invalid_records else pd.DataFrame(columns=["row_number", "record_id", "error_type", "problematic_field", "error_details", "raw_data"])

    metrics = {
        "total_rows": len(df),
        "valid_count": len(valid_records),
        "invalid_count": len(invalid_records),
        "file_duplicate_count": file_duplicates_count,
        "db_duplicate_count": db_duplicates_count,
        "total_valid_amount": float(valid_df["amount"].sum()) if not valid_df.empty else 0.0,
        "header_error": False
    }

    return {
        "valid_df": valid_df,
        "invalid_df": invalid_df,
        "metrics": metrics
    }
