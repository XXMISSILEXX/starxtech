#!/usr/bin/env python
"""Kiểm tra bất biến tổng hợp vấn đề tồn đọng trên dữ liệu thật.

Mặc định chỉ đọc. Dùng --recalculate để tính lại các trường tổng hợp đã lưu;
chế độ này không tạo audit log.

Dùng:

    .venv/bin/python scripts/verify_issue_rollup.py
    .venv/bin/python scripts/verify_issue_rollup.py --project-id 1
    .venv/bin/python scripts/verify_issue_rollup.py --recalculate

Mã thoát 0 nếu mọi bất biến đúng, 1 nếu có vi phạm.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.extensions import db
from app.models import IssueStatus, PersistentIssue, PersistentIssueSection


COMPLETED_STATUSES = {IssueStatus.RESOLVED.value, IssueStatus.CLOSED.value}
OPEN_STATUSES = {IssueStatus.OPEN.value, IssueStatus.PROCESSING.value}


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def ok(self, label: str, detail: str = "") -> None:
        print(f"  [ĐẠT ] {label}{(' — ' + detail) if detail else ''}")

    def fail(self, label: str, detail: str) -> None:
        print(f"  [LỖI ] {label} — {detail}")
        self.failures.append(f"{label}: {detail}")


def expected_rollup(sections):
    statuses = {section.status for section in sections}
    if not sections:
        status = IssueStatus.OPEN.value
    elif statuses <= {IssueStatus.CLOSED.value}:
        status = IssueStatus.CLOSED.value
    elif statuses <= COMPLETED_STATUSES:
        status = IssueStatus.RESOLVED.value
    elif IssueStatus.PROCESSING.value in statuses:
        status = IssueStatus.PROCESSING.value
    else:
        status = IssueStatus.OPEN.value

    due_dates = [
        section.due_date
        for section in sections
        if section.status in OPEN_STATUSES and section.due_date is not None
    ]
    return status, min(due_dates) if due_dates else None


def scoped_issues(project_id: int | None):
    query = PersistentIssue.query.filter(PersistentIssue.deleted_at.is_(None))
    if project_id is not None:
        query = query.filter(PersistentIssue.project_id == project_id)
    return query.order_by(PersistentIssue.id).all()


def sections_by_issue(issues):
    issue_ids = [issue.id for issue in issues]
    grouped = defaultdict(list)
    if not issue_ids:
        return grouped
    sections = (
        PersistentIssueSection.query.filter(
            PersistentIssueSection.persistent_issue_id.in_(issue_ids),
            PersistentIssueSection.deleted_at.is_(None),
        )
        .order_by(PersistentIssueSection.persistent_issue_id, PersistentIssueSection.sort_order, PersistentIssueSection.id)
        .all()
    )
    for section in sections:
        grouped[section.persistent_issue_id].append(section)
    return grouped


def check_rollups(report: Report, issues, sections):
    print("\n1. Status và hạn xử lý khớp hạng mục sống")
    status_mismatches = []
    due_date_mismatches = []
    for issue in issues:
        expected_status, expected_due_date = expected_rollup(sections[issue.id])
        if issue.status != expected_status:
            status_mismatches.append(
                f"vấn đề #{issue.id}: lưu {issue.status}, đúng phải là {expected_status}"
            )
        if issue.due_date != expected_due_date:
            due_date_mismatches.append(
                f"vấn đề #{issue.id}: lưu {issue.due_date}, đúng phải là {expected_due_date}"
            )
    if status_mismatches:
        for line in status_mismatches:
            report.fail("Status lệch", line)
    else:
        report.ok("Status", f"{len(issues)} vấn đề đều khớp")
    if due_date_mismatches:
        for line in due_date_mismatches:
            report.fail("Hạn xử lý lệch", line)
    else:
        report.ok("Hạn xử lý", f"{len(issues)} vấn đề đều khớp")


def recalculate_rollups(issues):
    """Update stored derived fields without creating audit-log entries."""
    from app.issues.services import recalculate_issue_rollup

    changed = 0
    for issue in issues:
        before = (issue.status, issue.due_date, issue.closed_date)
        recalculate_issue_rollup(issue)
        after = (issue.status, issue.due_date, issue.closed_date)
        changed += before != after
    db.session.commit()
    print(f"Đã tính lại {len(issues)} vấn đề; {changed} vấn đề thay đổi.")


def check_closed_dates(report: Report, issues):
    print("\n2. Ngày đóng nhất quán với status")
    mismatches = [
        f"vấn đề #{issue.id}: status={issue.status}, closed_date={issue.closed_date}"
        for issue in issues
        if (issue.closed_date is not None) != (issue.status == IssueStatus.CLOSED.value)
    ]
    if mismatches:
        for line in mismatches:
            report.fail("Ngày đóng lệch", line)
    else:
        report.ok("Ngày đóng", f"{len(issues)} vấn đề đều nhất quán")


def check_duplicate_categories(report: Report, sections):
    print("\n3. Mỗi loại hạng mục chỉ một lần trong mỗi vấn đề")
    duplicates = []
    for issue_id, issue_sections in sections.items():
        counts = Counter(section.report_category_id for section in issue_sections)
        for category_id, total in counts.items():
            if total > 1:
                duplicates.append(
                    f"vấn đề #{issue_id}, loại #{category_id}: {total} hạng mục sống"
                )
    if duplicates:
        for line in duplicates:
            report.fail("Trùng loại", line)
    else:
        report.ok("Không trùng loại", "không có vấn đề nào vi phạm")


def summarise(issues, sections):
    print("\n4. Quy mô dữ liệu hiện tại")
    total_sections = sum(len(issue_sections) for issue_sections in sections.values())
    statuses = Counter(issue.status for issue in issues)
    print(f"  vấn đề chưa xoá: {len(issues)}")
    print(f"  hạng mục chưa xoá: {total_sections}")
    print("  phân bố vấn đề theo status:")
    for status in (IssueStatus.OPEN.value, IssueStatus.PROCESSING.value, IssueStatus.RESOLVED.value, IssueStatus.CLOSED.value):
        print(f"    {status}: {statuses[status]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", type=int, default=None, help="Chỉ kiểm một dự án")
    parser.add_argument(
        "--recalculate",
        action="store_true",
        help="Tính lại status, due_date và closed_date từ hạng mục sống (không ghi audit)",
    )
    args = parser.parse_args()

    app = create_app()
    report = Report()
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        masked = uri.split("@")[-1] if "@" in uri else uri
        print(f"Kiểm tổng hợp vấn đề trên database: …@{masked}")
        if args.project_id is not None:
            print(f"Phạm vi: chỉ dự án #{args.project_id}")

        issues = scoped_issues(args.project_id)
        sections = sections_by_issue(issues)
        if args.recalculate:
            recalculate_rollups(issues)
            db.session.expire_all()
            issues = scoped_issues(args.project_id)
            sections = sections_by_issue(issues)
        check_rollups(report, issues, sections)
        check_closed_dates(report, issues)
        check_duplicate_categories(report, sections)
        summarise(issues, sections)

    print("\n" + "=" * 64)
    if report.failures:
        print(f"KẾT QUẢ: {len(report.failures)} vi phạm cần xử lý")
        for line in report.failures:
            print(f"  - {line}")
        return 1
    print("KẾT QUẢ: mọi bất biến đúng")
    return 0


if __name__ == "__main__":
    sys.exit(main())
