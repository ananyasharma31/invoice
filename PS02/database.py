"""
Database Management Module for Invoice & Payment Import System
Handles SQLite database connection, schema initialization, record insertion,
duplicate ID querying, and audit logging for invalid records.
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import Set, List, Dict, Any, Tuple, Optional
import os

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "reconciliation.db")


def get_db_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Returns a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initializes SQLite database tables if they do not exist."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()

        # Invoices Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                invoice_id TEXT PRIMARY KEY,
                customer_name TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_date TEXT NOT NULL,
                description TEXT,
                batch_id TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Payments Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                payment_id TEXT PRIMARY KEY,
                invoice_id TEXT,
                customer_name TEXT NOT NULL,
                amount REAL NOT NULL,
                transaction_date TEXT NOT NULL,
                description TEXT,
                payment_method TEXT,
                batch_id TEXT,
                imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Invalid Records / Audit Log Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invalid_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_type TEXT NOT NULL,
                record_id TEXT,
                batch_id TEXT,
                error_type TEXT NOT NULL,
                error_details TEXT NOT NULL,
                raw_record_json TEXT,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Matches Table (Module 2: Intelligent Matching)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                match_id TEXT PRIMARY KEY,
                invoice_id TEXT NOT NULL,
                payment_id TEXT NOT NULL,
                confidence TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                matching_evidence TEXT,
                review_flags TEXT,
                invoice_amount REAL,
                payment_amount REAL,
                amount_diff REAL,
                status TEXT DEFAULT 'Suggested',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Allocations Table (Module 3: Match Review & Reconciliation)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS allocations (
                allocation_id TEXT PRIMARY KEY,
                invoice_id TEXT NOT NULL,
                payment_id TEXT NOT NULL,
                allocated_amount REAL NOT NULL,
                status TEXT NOT NULL, -- 'CONFIRMED' or 'REJECTED'
                decision_by TEXT DEFAULT 'User',
                user_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
    finally:
        conn.close()


def get_existing_ids(db_path: str = DEFAULT_DB_PATH, table_name: str = "invoices", id_column: str = "invoice_id") -> Set[str]:
    """Retrieves all existing primary keys from the specified table to prevent DB duplicates."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT {id_column} FROM {table_name}")
        rows = cursor.fetchall()
        return {str(row[0]).strip().upper() for row in rows if row[0] is not None}
    except sqlite3.OperationalError:
        return set()
    finally:
        conn.close()


def insert_invoices(df_valid, batch_id: str, db_path: str = DEFAULT_DB_PATH) -> Tuple[int, int]:
    """
    Inserts validated invoice records into SQLite.
    Returns (inserted_count, skipped_count).
    """
    init_db(db_path)
    if df_valid is None or df_valid.empty:
        return 0, 0

    inserted_count = 0
    skipped_count = 0

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        for _, row in df_valid.iterrows():
            inv_id = str(row.get("invoice_id", "")).strip()
            cust_name = str(row.get("customer_name", "")).strip()
            amount = float(row.get("amount", 0.0))
            txn_date = str(row.get("transaction_date", "")).strip()
            desc = str(row.get("description", "")).strip() if "description" in row else ""

            try:
                cursor.execute("""
                    INSERT INTO invoices (invoice_id, customer_name, amount, transaction_date, description, batch_id, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (inv_id, cust_name, amount, txn_date, desc, batch_id, now_ts))
                inserted_count += 1
            except sqlite3.IntegrityError:
                # Primary key collision
                skipped_count += 1

        conn.commit()
    finally:
        conn.close()

    return inserted_count, skipped_count


def insert_payments(df_valid, batch_id: str, db_path: str = DEFAULT_DB_PATH) -> Tuple[int, int]:
    """
    Inserts validated payment records into SQLite.
    Returns (inserted_count, skipped_count).
    """
    init_db(db_path)
    if df_valid is None or df_valid.empty:
        return 0, 0

    inserted_count = 0
    skipped_count = 0

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        for _, row in df_valid.iterrows():
            pmt_id = str(row.get("payment_id", "")).strip()
            inv_id = str(row.get("invoice_id", "")).strip()
            cust_name = str(row.get("customer_name", "")).strip()
            amount = float(row.get("amount", 0.0))
            txn_date = str(row.get("transaction_date", "")).strip()
            desc = str(row.get("description", "")).strip() if "description" in row else ""
            pmt_method = str(row.get("payment_method", "Bank Transfer")).strip() if "payment_method" in row else "Bank Transfer"

            try:
                cursor.execute("""
                    INSERT INTO payments (payment_id, invoice_id, customer_name, amount, transaction_date, description, payment_method, batch_id, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (pmt_id, inv_id, cust_name, amount, txn_date, desc, pmt_method, batch_id, now_ts))
                inserted_count += 1
            except sqlite3.IntegrityError:
                # Primary key collision
                skipped_count += 1

        conn.commit()
    finally:
        conn.close()

    return inserted_count, skipped_count


def log_invalid_records(invalid_records: List[Dict[str, Any]], record_type: str, batch_id: str, db_path: str = DEFAULT_DB_PATH) -> int:
    """Stores rejected/invalid records into audit table for correction tracking."""
    init_db(db_path)
    if not invalid_records:
        return 0

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        for rec in invalid_records:
            rec_id = str(rec.get("record_id", rec.get("invoice_id", rec.get("payment_id", "UNKNOWN"))))
            err_type = str(rec.get("error_type", "VALIDATION_FAILED"))
            err_details = str(rec.get("error_details", "Unknown error"))
            raw_json = json.dumps(rec.get("raw_data", rec), default=str)

            cursor.execute("""
                INSERT INTO invalid_records (record_type, record_id, batch_id, error_type, error_details, raw_record_json, logged_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (record_type, rec_id, batch_id, err_type, err_details, raw_json, now_ts))

        conn.commit()
    finally:
        conn.close()

    return len(invalid_records)


def save_matches(matches_df: Any, db_path: str = DEFAULT_DB_PATH) -> int:
    """Stores intelligent transaction matches in the SQLite database."""
    init_db(db_path)
    if matches_df is None or matches_df.empty:
        return 0

    conn = get_db_connection(db_path)
    inserted_count = 0
    try:
        cursor = conn.cursor()
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        for _, row in matches_df.iterrows():
            inv_id = str(row.get("invoice_id", "")).strip()
            pmt_id = str(row.get("payment_id", "")).strip()
            match_id = f"MATCH-{inv_id}-{pmt_id}"
            conf = str(row.get("confidence", "Review required"))
            conf_score = float(row.get("confidence_score", 0.0))
            evidence = str(row.get("matching_evidence", ""))
            flags = str(row.get("review_flags", ""))
            inv_amt = float(row.get("invoice_amount", 0.0))
            pmt_amt = float(row.get("payment_amount", 0.0))
            amt_diff = float(row.get("amount_diff", 0.0))

            cursor.execute("""
                INSERT OR REPLACE INTO matches (
                    match_id, invoice_id, payment_id, confidence, confidence_score,
                    matching_evidence, review_flags, invoice_amount, payment_amount,
                    amount_diff, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Suggested', ?)
            """, (match_id, inv_id, pmt_id, conf, conf_score, evidence, flags, inv_amt, pmt_amt, amt_diff, now_ts))
            inserted_count += 1

        conn.commit()
    finally:
        conn.close()

    return inserted_count


def update_match_status(match_id: str, new_status: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Updates status of a match (e.g. 'Approved', 'Rejected', 'Suggested')."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE matches SET status = ? WHERE match_id = ?", (new_status, match_id))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def record_allocation(
    invoice_id: str,
    payment_id: str,
    allocated_amount: float,
    status: str = "CONFIRMED",
    user_notes: str = "",
    decision_by: str = "User",
    db_path: str = DEFAULT_DB_PATH
) -> str:
    """
    Records user confirmation or rejection of a match.
    Persists decision in SQLite to prevent reintroducing rejected suggestions.
    """
    init_db(db_path)
    inv_id = str(invoice_id).strip().upper()
    pmt_id = str(payment_id).strip().upper()
    allocation_id = f"ALC-{inv_id}-{pmt_id}"
    now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO allocations (
                allocation_id, invoice_id, payment_id, allocated_amount,
                status, decision_by, user_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (allocation_id, inv_id, pmt_id, float(allocated_amount), status.upper(), decision_by, user_notes, now_ts, now_ts))
        
        # Also update matches table status if present
        match_id = f"MATCH-{inv_id}-{pmt_id}"
        cursor.execute("UPDATE matches SET status = ? WHERE match_id = ?", (status.capitalize(), match_id))

        conn.commit()
    finally:
        conn.close()

    return allocation_id


def get_allocations(db_path: str = DEFAULT_DB_PATH, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves allocation decisions from SQLite."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM allocations WHERE status = ? ORDER BY created_at DESC", (status.upper(),))
        else:
            cursor.execute("SELECT * FROM allocations ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_rejected_pairs(db_path: str = DEFAULT_DB_PATH) -> Set[Tuple[str, str]]:
    """
    Retrieves all (invoice_id, payment_id) pairs explicitly marked as REJECTED by the user.
    Prevents rejected suggestions from ever being silently reintroduced as matches.
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT invoice_id, payment_id FROM allocations WHERE status = 'REJECTED'")
        rows = cursor.fetchall()
        return {(str(r[0]).strip().upper(), str(r[1]).strip().upper()) for r in rows}
    finally:
        conn.close()


def delete_allocation(allocation_id: str, db_path: str = DEFAULT_DB_PATH) -> bool:
    """Removes an allocation record and resets matching status."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM allocations WHERE allocation_id = ?", (allocation_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def fetch_table_data(table_name: str, limit: int = 500, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves records from specified table as a list of dictionaries."""
    init_db(db_path)
    allowed_tables = {"invoices", "payments", "invalid_records", "matches", "allocations"}
    if table_name not in allowed_tables:
        raise ValueError(f"Unauthorized table access: {table_name}")

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY rowid DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_database_stats(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Returns total row counts and amount statistics from the SQLite database."""
    init_db(db_path)
    stats = {}
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()

        # Invoices stats
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0.0) FROM invoices")
        inv_row = cursor.fetchone()
        stats["total_invoices"] = inv_row[0]
        stats["total_invoice_amount"] = inv_row[1]

        # Payments stats
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(amount), 0.0) FROM payments")
        pmt_row = cursor.fetchone()
        stats["total_payments"] = pmt_row[0]
        stats["total_payment_amount"] = pmt_row[1]

        # Invalid logs stats
        cursor.execute("SELECT COUNT(*) FROM invalid_records")
        stats["total_invalid_logs"] = cursor.fetchone()[0]

        # Matches stats
        cursor.execute("SELECT COUNT(*) FROM matches")
        stats["total_matches"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM matches WHERE confidence = 'High'")
        stats["high_matches"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM matches WHERE confidence = 'Review required'")
        stats["review_required_matches"] = cursor.fetchone()[0]

        # Allocations stats (Module 3)
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(allocated_amount), 0.0) FROM allocations WHERE status = 'CONFIRMED'")
        alc_row = cursor.fetchone()
        stats["confirmed_allocations_count"] = alc_row[0]
        stats["confirmed_allocated_amount"] = alc_row[1]

        cursor.execute("SELECT COUNT(*) FROM allocations WHERE status = 'REJECTED'")
        stats["rejected_allocations_count"] = cursor.fetchone()[0]
    finally:
        conn.close()

    return stats


def reset_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """Drops tables and reinitializes the database."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS invoices")
        cursor.execute("DROP TABLE IF EXISTS payments")
        cursor.execute("DROP TABLE IF EXISTS invalid_records")
        cursor.execute("DROP TABLE IF EXISTS matches")
        cursor.execute("DROP TABLE IF EXISTS allocations")
        conn.commit()
    finally:
        conn.close()
    init_db(db_path)
