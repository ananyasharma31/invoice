"""
Sample Data Generator
Generates sample invoice and payment CSV files containing realistic mix of
valid records, messy data (requiring normalization), and intentionally invalid
records (missing fields, invalid amounts, unparseable dates, and duplicate records).
"""

import os

INVOICE_SAMPLE_CSV = """invoice_id,customer_name,amount,transaction_date,description
INV-101,Acme Corp,5000.00,2024-01-10,Enterprise Consulting Package
INV-102,Global Logistics LLC,3000.00,2024-01-12,Air Freight Handling
INV-103,Apex Innovations Inc.,7000.00,2024-01-15,Cloud Infrastructure Build
INV-2024-001,  acme corporations  , $1500.50 ,2024-01-15,Consulting Services & Setup
INV-2024-002,Global Logistics LLC,4200.00,18/01/2024,Freight and Cargo Handling
INV-2024-003,Apex Innovations Inc.,750.25,2024/02/01,Cloud Software Subscription
INV-2024-004,john doe & sons,12500.00,05-Feb-2024,Enterprise Annual License
INV-2024-005,Starlight Media,950.00,2024-02-12,Video Production Retainer
INV-2024-006,,1200.00,2024-02-15,Web Development (Missing Customer Name)
INV-2024-007,Pinnacle Systems,-350.00,2024-02-18,Negative Amount Error
INV-2024-008,Nexus Dynamics,ZERO,2024-02-20,Non-Numeric Amount Error
,Quantum Solutions,2500.00,2024-02-22,Missing Invoice ID Error
INV-2024-009,Beacon Retail,1800.00,invalid-date-31,Unparseable Date Error
INV-2024-001,  ACME CORPORATIONS  ,1500.50,2024-01-15,Duplicate of INV-001 in file
INV-2024-010,Vortex Ventures,3100.75,2024-03-01,Marketing Strategy
"""

PAYMENT_SAMPLE_CSV = """payment_id,invoice_id,customer_name,amount,transaction_date,payment_method,description
PAY-201,INV-101,Acme Corp,5000.00,2024-01-14,Wire Transfer,Full Settlement for INV-101
PAY-202,,Global Logistics,3000.00,2024-01-16,ACH,Freight payment without explicit invoice ID
PAY-203,INV-103,Apex Innovations Inc,6500.00,2024-01-20,Wire Transfer,Partial Payment for INV-103
PAY-2024-001,INV-2024-001,Acme Corporations,$1500.50,2024-01-20,Wire Transfer,Full Settlement for INV-001
PAY-2024-002,INV-2024-002,global logistics llc,2000.00,22/01/2024,ACH,Partial Payment Part 1
PAY-2024-003,INV-2024-002,Global Logistics LLC,2200.00,28/01/2024,ACH,Final Settlement Part 2
PAY-2024-004,INV-2024-003,Apex Innovations Inc.,$750.25,05-Feb-2024,Credit Card,Software Subscription Fee
PAY-2024-005,INV-2024-004,John Doe & Sons,12500.00,2024-02-10,Check,Annual License Renewal
PAY-2024-006,INV-2024-005,starlight media,-150.00,2024-02-16,Credit Card,Negative Amount Payment
PAY-2024-007,,Beacon Retail,1800.00,2024-02-25,Wire Transfer,Missing Referenced Invoice ID
PAY-2024-008,INV-2024-009,,900.00,2024-02-26,Cash,Missing Customer Name
PAY-2024-009,INV-2024-010,Vortex Ventures,FREE,2024-03-05,Credit Card,Invalid Amount String
PAY-2024-001,INV-2024-001,Acme Corporations,1500.50,2024-01-20,Wire Transfer,Duplicate Payment ID in file
PAY-2024-010,INV-2024-010,Vortex Ventures,3100.75,2024-03-10,ACH,Full payment settlement
"""


def create_sample_files(target_dir: str = None) -> dict:
    """Writes sample files to disk and returns paths."""
    if target_dir is None:
        target_dir = os.path.dirname(__file__)

    os.makedirs(target_dir, exist_ok=True)
    inv_path = os.path.join(target_dir, "sample_invoices.csv")
    pmt_path = os.path.join(target_dir, "sample_payments.csv")

    with open(inv_path, "w", encoding="utf-8") as f:
        f.write(INVOICE_SAMPLE_CSV.strip())

    with open(pmt_path, "w", encoding="utf-8") as f:
        f.write(PAYMENT_SAMPLE_CSV.strip())

    return {
        "invoice_csv": inv_path,
        "payment_csv": pmt_path
    }


if __name__ == "__main__":
    paths = create_sample_files()
    print("Sample CSV files generated successfully:")
    for k, v in paths.items():
        print(f" - {k}: {v}")
