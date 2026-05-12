from __future__ import annotations

# Closed-set of UAE-BFSI document types. The vision model must pick
# `document_type` from this list verbatim (or use "Uncategorized" as the
# fallback). The reasoner treats the same list as canonical folder names —
# never invents new ones.
#
# Tailored to UAE banking / regulatory context:
#   - Identity: Emirates ID, UAE Residence Visa, Trade License (no PAN/Aadhaar).
#   - Payments: IBAN transfers + SWIFT (no NEFT/RTGS/UPI).
#   - Direct debits via UAE Direct Debit System (no ECS).
#   - Tax: 5% VAT + Corporate Tax (no GST/TDS).
#   - Compliance: CBUAE filings, goAML (UAE FIU), FATCA/CRS, UBO.
#   - Credit bureau: AECB (Al Etihad Credit Bureau).
#   - HR: WPS payroll + End-of-Service Gratuity (no PF).
#   - Islamic finance: Sukuk, Murabaha, Ijara, Wakala, Mudaraba, Takaful.
#   - Exchanges: DFM (Dubai) / ADX (Abu Dhabi) — no Demat.
ALLOWED_DOCUMENT_TYPES: tuple[str, ...] = (
    "Account Opening Forms",
    "KYC Documents",
    "Emirates ID Copies",
    "Passport Copies",
    "UAE Residence Visa Copies",
    "Driver's License Copies",
    "Trade License Copies",
    "Memorandum of Association (MOA)",
    "Articles of Association (AOA)",
    "Establishment Card Copies",
    "Signature Cards",
    "Power of Attorney Documents",
    "Address Proof Documents",
    "Ejari Registration Copies",
    "UBO (Ultimate Beneficial Owner) Declarations",
    "Salary Certificates",
    "Salary Transfer Letters",
    "Nominee Forms",
    "Customer Agreements",
    "Passbooks",
    "Account Statements",
    "Bank Statements",
    "Cheque Books",
    "Cheque Deposit Slips",
    "Deposit Slips",
    "Withdrawal Forms",
    "Payment Vouchers",
    "Bills",
    "Invoices",
    "Receipts",
    "Transfer Instructions",
    "Wire Transfer Requests",
    "SWIFT Transaction Records",
    "IBAN Transfer Forms",
    "Foreign Exchange Forms",
    "Direct Debit Mandate Forms",
    "Standing Instruction Forms",
    "Debit Card Applications",
    "Credit Card Applications",
    "ATM Dispute Forms",
    "Expense Reimbursement Documents",
    "Loan Applications",
    "Personal Loan Documents",
    "Mortgage Papers",
    "Collateral Documents",
    "Loan Agreements",
    "EMI Schedules",
    "Loan Modification Forms",
    "Loan Extension Forms",
    "Foreclosure Records",
    "Recovery Records",
    "Credit Reports (AECB)",
    "Insurance Documents",
    "Takaful Policies",
    "Sukuk Documents",
    "Murabaha Agreements",
    "Ijara Agreements",
    "Wakala Agreements",
    "Mudaraba Agreements",
    "Investment Portfolio Statements",
    "DFM / ADX Account Forms",
    "Fixed Deposit Receipts (FDR)",
    "Treasury Reports",
    "Locker Agreements",
    "Safe Deposit Access Logs",
    "Account Closure Forms",
    "Dormant Account Activation Forms",
    "Customer Due Diligence (CDD) Records",
    "Enhanced Due Diligence (EDD) Reports",
    "AML Monitoring Reports",
    "Suspicious Transaction Reports (STRs)",
    "goAML Filings",
    "Cash Transaction Reports (CTR)",
    "Sanctions Screening Reports",
    "PEP Screening Records",
    "FATCA Forms",
    "CRS (Common Reporting Standard) Forms",
    "Internal Audit Reports",
    "CBUAE Regulatory Filings",
    "Risk Assessment Reports",
    "Compliance Certificates",
    "Fraud Investigation Reports",
    "Cybersecurity Incident Reports",
    "Business Continuity Plans",
    "Disaster Recovery Documents",
    "VAT Records",
    "VAT Return Filings",
    "Corporate Tax Filings",
    "Withholding Tax Records",
    "Employment Contracts",
    "Payroll Records (WPS)",
    "End of Service Gratuity Records",
    "Non-Disclosure Agreements (NDAs)",
    "Vendor Agreements",
    "Vendor KYC Documents",
    "Customer Complaint Records",
    "Board Meeting Minutes",
    "Policy Documents",
    "SOP (Standard Operating Procedure) Manuals",
    "Training Records",
)


def _numbered(items: tuple[str, ...]) -> str:
    return "\n".join(f"{i + 1}. {name}" for i, name in enumerate(items))


VISION_SYSTEM = (
    "You extract structured metadata from a single page of a BFSI (banking, "
    "financial services and insurance) document. Respond with ONLY a single "
    "JSON object on one line and nothing else. No prose, no Markdown fences, "
    "no comments."
)


VISION_USER_TEMPLATE = (
    "Extract metadata from this page. Return JSON with EXACTLY these keys:\n"
    "{"
    '"document_type": "<one of the allowed types listed below, or \\"Uncategorized\\">",'
    '"version": "<version label visible on the page, or null>",'
    '"date": "<ISO date YYYY-MM-DD visible on the page, or null>",'
    '"person_name": "<primary natural person on the page, or null>",'
    '"entity_name": "<primary organization on the page, or null>",'
    '"confidence": <number from 0.0 to 1.0>'
    "}\n"
    "Use null (not the string \"null\") for fields you cannot determine. "
    "Output one JSON object only.\n\n"
    "Rules for entity_name vs person_name:\n"
    "- entity_name is the issuing or owning organisation visible on the page "
    "(e.g., the employer on a Salary Certificate, the bank on an Account "
    "Statement, the licensing authority on a Trade License). The filing "
    "system uses entity_name first when both are present, so prefer the "
    "organisation that *owns* the document rather than any incidental party.\n"
    "- person_name is reserved for the natural person who is the SUBJECT of "
    "the document (cardholder, employee, account holder, ID holder).\n\n"
    "ALLOWED document_type values (you MUST pick the closest match verbatim "
    "from this list — case, spaces, punctuation and parentheses included; "
    "use \"Uncategorized\" only if no entry plausibly applies):\n"
    + _numbered(ALLOWED_DOCUMENT_TYPES)
)


# REASONER_* prompts were removed when the reasoner LLM step was dropped:
# filing paths are now computed deterministically from vision metadata in
# sidecar/dms/pipeline/filer.py:compute_final_key.


TEXT_SYSTEM = (
    "You extract structured metadata from a UAE BFSI document's text content "
    "(extracted from a CSV / spreadsheet / Word doc / audio or video "
    "transcript). Respond with ONLY a single JSON object on one line — no "
    "prose, no Markdown fences, no comments."
)


TEXT_USER_TEMPLATE = (
    "Classify the following text into one of the allowed UAE BFSI document "
    "types. Return JSON with EXACTLY these keys: document_type, version, "
    "date, person_name, entity_name, confidence. Use null (not the string "
    "\"null\") for fields you cannot determine.\n\n"
    "Entity vs person rules (same as the vision pipeline):\n"
    "- entity_name = the issuing or owning organisation (employer, bank, "
    "licensing authority). The filing system uses entity_name first when "
    "both are present, so prefer the organisation that *owns* the document.\n"
    "- person_name = the natural person who is the SUBJECT of the document "
    "(cardholder, employee, account holder, ID holder).\n"
    "- For audio/video transcripts, infer entity / person from what is "
    "actually said in the clip.\n\n"
    "ALLOWED document_type values (verbatim, case-sensitive; "
    "\"Uncategorized\" only as a last resort):\n"
    + _numbered(ALLOWED_DOCUMENT_TYPES)
    + "\n\n--- DOCUMENT CONTENT (truncated) ---\n{content}\n--- END CONTENT ---"
)
