"""Generate synthetic single-page PDFs for the engine-smoke run.

Each PDF holds plain-text content that looks roughly like a real document so
the vision pipeline has something to extract (document_type, date, entity).
The files have stable names so smoke runs are reproducible.
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


FIXTURES: list[tuple[str, list[str]]] = [
    (
        "invoice_acme_2026-05-11.pdf",
        [
            "INVOICE",
            "",
            "ACME Corp",
            "123 Example Street",
            "",
            "Invoice number: INV-2026-0042",
            "Date: 2026-05-11",
            "Bill to: Allys AI",
            "",
            "Description           Qty   Unit Price   Total",
            "Widget                 10        $25.00   $250.00",
            "Sprocket                4        $99.00   $396.00",
            "",
            "Total due: $646.00",
        ],
    ),
    (
        "contract_v2_2026-05-11.pdf",
        [
            "SERVICE AGREEMENT",
            "Version 2",
            "",
            "Effective date: 2026-05-11",
            "Between: Allys AI ('Customer')",
            "And: Initech ('Provider')",
            "",
            "Section 1: Scope",
            "Provider will deliver software services as described.",
            "",
            "Section 2: Fees",
            "Customer agrees to pay $1,000 per month.",
        ],
    ),
]


def write_fixtures(target_dir: Path) -> list[Path]:
    target_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, lines in FIXTURES:
        out = target_dir / name
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # A4 portrait points
        y = 72
        for line in lines:
            page.insert_text((72, y), line, fontname="helv", fontsize=11)
            y += 18
        doc.save(str(out))
        doc.close()
        written.append(out)
    return written


if __name__ == "__main__":
    import sys

    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".smoke") / "inbox"
    files = write_fixtures(out_dir)
    for f in files:
        print(f"wrote {f}")
