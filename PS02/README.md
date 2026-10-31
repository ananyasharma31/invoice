# Financial Reconciliation Engine
### Module 1: Data Import and Validation
### Module 2: Intelligent Transaction Matching
### Module 3: Match Review and Reconciliation

A complete, production-grade financial reconciliation pipeline built with **Python**, **pandas**, **RapidFuzz**, **Decimal**, **SQLite**, and **Streamlit**.

---

## 🎯 Objectives & Capabilities

### Module 1: Data Import & Validation
- **Interactive File Upload**: Upload Invoices and Payments CSV files with flexible column alias auto-detection.
- **Required Fields Validation**: Validates presence of `invoice_id`, `customer_name`, `amount`, and `transaction_date`.
- **Data Normalization**:
  - **Customer Names**: Cleans whitespace, trims stray punctuation, and normalizes to standard Title Case.
  - **Transaction Dates**: Converts international formats (`YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, `05-Feb-2024`) into ISO `YYYY-MM-DD`.
  - **Amounts**: Removes currency symbols (`$`, `€`, `£`, `₹`, `¥`) and commas, parses to positive floats, flags negative/non-numeric values.
  - **Descriptions**: Normalizes whitespace and sets clean defaults.
- **Discrepancy & Duplicate Detection**: Missing fields, negative/zero amounts, unparseable dates, in-file duplicates, and SQLite primary key collisions.
- **SQLite Database Persistence**: Stores clean records in `invoices` and `payments` tables; rejected records stored in `invalid_records` audit log.

### Module 2: Intelligent Transaction Matching
- **Invoice Reference & Customer Matching**: Cross-references invoice numbers in payments or extracts them from descriptions.
- **RapidFuzz Fuzzy Matching**: Compares customer names using token sort ratios while stripping legal corporate suffixes (`LLC`, `Inc`, `Corp`, etc.).
- **Amount Comparison & Discrepancies**: Compares invoice vs payment amounts; flags partial payments, deductions, and discrepancies (`AMOUNT_MISMATCH`).
- **Date Plausibility Analysis**: Evaluates settlement window in days; detects and flags anomalous payments predating invoice issue dates (`DATE_ANOMALY`).
- **Confidence Scoring & Evidence**:
  - **High Confidence**: Exact reference and matching amount (e.g., `INV-101` and `PAY-201`).
  - **Medium Confidence**: Similar customer name via RapidFuzz and matching amount (e.g., `INV-102` and `PAY-202`).
  - **Review Required**: Discrepancies or ambiguities flagged for manual auditor review (e.g., `INV-103` and `PAY-203`).

### Module 3: Match Review and Reconciliation
- **Interactive Match Review Queue**:
  - Review all suggested pairs with side-by-side evidence, RapidFuzz similarity, amount differences, and discrepancy flags.
  - Quick action: Batch confirm all High-Confidence matches.
- **User Decisions (Confirm, Reject, Manual Allocation)**:
  - **Confirm Match**: Officially allocates funds and updates invoice balances.
  - **Reject Match**: Stores rejection in SQLite; **prevents rejected suggestions from ever being silently reintroduced as matches**.
  - **Manual Match**: Allows accountants to pair any unallocated payment with an invoice and set a custom allocation amount.
- **Strict Anti-Double-Allocation Guard**:
  - Tracks allocated amounts per payment: $\sum \text{allocated} \le \text{payment\_amount}$.
  - Blocks any attempt to allocate a payment more than once or beyond its remaining unallocated capacity.
- **High-Precision Decimal Balance Ledger**:
  - Exact formula:
    $$\text{Outstanding Balance} = \text{Invoice Amount} - \text{Confirmed Allocations}$$
  - Formatted like prompt example:
    - `INV-101`: Amount $5,000 | Confirmed Paid: $5,000 | Outstanding: $0 (`PAID`)
    - `INV-102`: Amount $3,000 | Confirmed Paid: $2,000 | Outstanding: $1,000 (`PARTIALLY PAID`)
    - `INV-103`: Amount $7,000 | Confirmed Paid: $0 | Outstanding: $7,000 (`UNPAID`)
- **Unresolved Transactions Report**:
  - Unsettled invoices needing follow-up (Unpaid or Partially Paid).
  - Unallocated payment balances needing refund or assignment.
  - Full audit trail of user decisions in SQLite.

---

## 📁 Project Structure

```
invoice_import_module/
│
├── app.py                  # Streamlit dashboard (Modules 1, 2 & 3 UI)
├── validator.py            # Module 1: Normalization & validation engine
├── matcher.py              # Module 2: RapidFuzz intelligent matching engine
├── reconciliation.py       # Module 3: Decimal balance calculations & allocation guards
├── database.py             # SQLite DB manager (invoices, payments, matches, allocations)
├── sample_data.py          # Demo datasets with prompt test cases
├── test_module.py          # Module 1 unit tests (5 passed)
├── test_matcher.py         # Module 2 unit tests (5 passed)
├── test_reconciliation.py  # Module 3 unit tests (4 passed)
├── sample_invoices.csv     # Pre-generated sample invoices
├── sample_payments.csv     # Pre-generated sample payments
├── requirements.txt        # Python dependencies
└── run_app.bat             # 1-click batch launcher for Windows
```

The application database and test databases are created locally when needed and are excluded from version control.

---

## 🚀 How to Run

### Step 1: Open Terminal / PowerShell
```powershell
cd path\to\PS02
```

### Step 2: Launch Streamlit Dashboard
```powershell
streamlit run app.py
```
*(Or simply double-click `run_app.bat` in Windows File Explorer)*

The dashboard will open automatically in your browser at `http://localhost:8501`.

---

## 🧪 Running Automated Tests

Run the complete test suite (all 14 tests across Modules 1, 2, and 3):
```powershell
python -m unittest discover -s . -p "test_*.py"
```

---

## 📊 Database Schema (SQLite)

- **`invoices`**: `invoice_id (PK)`, `customer_name`, `amount`, `transaction_date`, `description`, `batch_id`, `imported_at`.
- **`payments`**: `payment_id (PK)`, `invoice_id`, `customer_name`, `amount`, `transaction_date`, `description`, `payment_method`, `batch_id`, `imported_at`.
- **`matches`**: `match_id (PK)`, `invoice_id`, `payment_id`, `confidence`, `confidence_score`, `matching_evidence`, `review_flags`, `invoice_amount`, `payment_amount`, `amount_diff`, `status`, `created_at`.
- **`allocations`**: `allocation_id (PK)`, `invoice_id`, `payment_id`, `allocated_amount`, `status (CONFIRMED/REJECTED)`, `decision_by`, `user_notes`, `created_at`, `updated_at`.
- **`invalid_records`**: `id (PK)`, `record_type`, `record_id`, `batch_id`, `error_type`, `error_details`, `raw_record_json`, `logged_at`.
