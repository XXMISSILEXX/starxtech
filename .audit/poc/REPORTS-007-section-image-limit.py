# REPORTS-007 was closed on 2026-08-04 by accepting the fixed 10-image contract.
"""Regression proof for REPORTS-007 (read-only, intentionally fails at HEAD).

Run:
    .venv/bin/python -m pytest -q .audit/poc/REPORTS-007-section-image-limit.py
"""

from app.reports.constants import MAX_ATTACHMENTS_PER_REPORT_SECTION


def test_daily_report_contract_allows_at_most_three_images_per_section():
    # AGENTS.md:39 and :64 are the retained product contract.  HEAD is 10.
    assert MAX_ATTACHMENTS_PER_REPORT_SECTION == 3
