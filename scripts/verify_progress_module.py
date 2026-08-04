#!/usr/bin/env python
"""Kiểm tra bất biến của mô đun tiến độ thi công trên dữ liệu thật.

CHỈ ĐỌC. Script không ghi, không sửa, không xoá bất cứ thứ gì.

Unit test chạy trên dữ liệu giả nên không thể phát hiện dữ liệu thật đã lệch bất
biến — ví dụ ``completed_quantity`` không còn khớp tổng phiếu sau một lần retry, hay
một hạng mục lưu số mịn hơn ``decimal_places`` đã khai nên bị làm tròn sai khi hiển
thị. Script này kiểm đúng những chỗ đó.

Dùng:

    .venv/bin/python scripts/verify_progress_module.py
    .venv/bin/python scripts/verify_progress_module.py --project-id 1

Mã thoát 0 nếu mọi bất biến đúng, 1 nếu có vi phạm.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app import create_app
from app.extensions import db
from app.models import (
    Permission,
    ProgressEntry,
    ProgressGroup,
    ProgressItem,
    ProgressType,
)

PROGRESS_PERMISSIONS = (
    "construction_progress.view",
    "construction_progress.create",
    "construction_progress.edit",
    "construction_progress.edit_all",
    "construction_progress.delete",
    "construction_progress.structure",
    "dashboards.progress.view",
)
CAPABILITY_COLUMNS = (
    "can_view_progress",
    "can_create_progress_entries",
    "can_edit_all_progress_entries",
    "can_manage_progress_structure",
)
ITEM_DATE_COLUMNS = ("planned_start_date", "planned_end_date", "actual_start_date")


def decimals_used(value: Decimal | None) -> int:
    """Số chữ số thập phân thực sự có nghĩa của một giá trị Numeric."""
    if value is None:
        return 0
    exponent = Decimal(value).normalize().as_tuple().exponent
    return max(0, -int(exponent))


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.notes: list[str] = []

    def ok(self, label: str, detail: str = "") -> None:
        print(f"  [ĐẠT ] {label}{(' — ' + detail) if detail else ''}")

    def fail(self, label: str, detail: str) -> None:
        print(f"  [LỖI ] {label} — {detail}")
        self.failures.append(f"{label}: {detail}")

    def note(self, label: str, detail: str) -> None:
        print(f"  [GHI ] {label} — {detail}")
        self.notes.append(f"{label}: {detail}")


def check_schema(report: Report) -> None:
    print("\n1. Schema database khớp model")
    rows = db.session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'progress_items'"
        )
    ).scalars()
    columns = set(rows)
    missing = [name for name in (*ITEM_DATE_COLUMNS, "decimal_places") if name not in columns]
    if missing:
        report.fail("Cột của progress_items", f"thiếu {', '.join(missing)} — chưa chạy flask db upgrade?")
    else:
        report.ok("Cột của progress_items", "đủ decimal_places và ba cột ngày")

    rows = db.session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'project_users'"
        )
    ).scalars()
    columns = set(rows)
    missing = [name for name in CAPABILITY_COLUMNS if name not in columns]
    if missing:
        report.fail("Cột capability của project_users", f"thiếu {', '.join(missing)}")
    else:
        report.ok("Cột capability của project_users", "đủ bốn cột")


def check_migration_head(report: Report) -> None:
    print("\n2. Migration đã ở revision mới nhất")
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        config = Config()
        config.set_main_option("script_location", "migrations")
        head = ScriptDirectory.from_config(config).get_current_head()
        current = db.session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except Exception as exc:  # pragma: no cover - phụ thuộc môi trường
        report.note("Không đọc được revision", f"{type(exc).__name__}")
        return
    if current == head:
        report.ok("Revision", f"{current} là head")
    else:
        report.fail("Revision", f"database ở {current} còn code ở {head} — cần flask db upgrade")


def check_permissions(report: Report) -> None:
    print("\n3. Permission đã được đồng bộ vào database")
    existing = {
        code
        for (code,) in db.session.query(Permission.code)
        .filter(Permission.code.in_(PROGRESS_PERMISSIONS))
        .all()
    }
    missing = [code for code in PROGRESS_PERMISSIONS if code not in existing]
    if missing:
        report.fail(
            "Permission code",
            f"thiếu {', '.join(missing)} — cần flask sync-permissions --apply-defaults",
        )
    else:
        report.ok("Permission code", f"đủ {len(PROGRESS_PERMISSIONS)} code")


def check_accumulation(report: Report, project_id: int | None) -> None:
    print("\n4. Lũy kế khớp tổng phiếu (bất biến quan trọng nhất)")
    items = ProgressItem.query
    if project_id is not None:
        items = items.filter(ProgressItem.project_id == project_id)
    items = items.all()

    sums: dict[int, Decimal] = defaultdict(lambda: Decimal(0))
    entry_query = db.session.query(ProgressEntry.progress_item_id, ProgressEntry.quantity)
    if project_id is not None:
        entry_query = entry_query.filter(ProgressEntry.project_id == project_id)
    for item_id, quantity in entry_query.all():
        sums[item_id] += Decimal(quantity)

    broken = []
    for item in items:
        expected = Decimal(item.opening_quantity) + sums[item.id]
        if Decimal(item.completed_quantity) != expected:
            broken.append(
                f"hạng mục #{item.id} '{item.name}': lưu {item.completed_quantity}, "
                f"đúng phải là {expected}"
            )
    if broken:
        for line in broken:
            report.fail("Lũy kế lệch", line)
    else:
        report.ok(
            "Lũy kế",
            f"{len(items)} hạng mục đều khớp opening_quantity cộng tổng phiếu",
        )


def check_declared_precision(report: Report, project_id: int | None) -> None:
    print("\n5. Không có số nào mịn hơn độ chính xác đã khai")
    items = ProgressItem.query
    if project_id is not None:
        items = items.filter(ProgressItem.project_id == project_id)
    violations = []
    for item in items.all():
        allowed = int(item.decimal_places or 0)
        for label, value in (
            ("khối lượng kế hoạch", item.planned_quantity),
            ("đã làm trước đó", item.opening_quantity),
            ("lũy kế", item.completed_quantity),
        ):
            if decimals_used(value) > allowed:
                violations.append(
                    f"hạng mục #{item.id} '{item.name}': {label} = {value} "
                    f"nhưng chỉ khai {allowed} chữ số thập phân"
                )
        for entry in item.entries:
            if decimals_used(entry.quantity) > allowed:
                violations.append(
                    f"phiếu #{entry.id} ngày {entry.report_date} của '{item.name}': "
                    f"{entry.quantity} vượt {allowed} chữ số thập phân"
                )
    if violations:
        for line in violations:
            report.fail("Độ chính xác", line)
    else:
        report.ok("Độ chính xác", "mọi giá trị nằm trong mức đã khai")


def check_dates(report: Report, project_id: int | None) -> None:
    print("\n6. Ngày kế hoạch hợp lệ")
    items = ProgressItem.query
    if project_id is not None:
        items = items.filter(ProgressItem.project_id == project_id)
    unpaired, reversed_dates = [], []
    for item in items.all():
        start, end = item.planned_start_date, item.planned_end_date
        if (start is None) != (end is None):
            unpaired.append(f"hạng mục #{item.id} '{item.name}'")
        if start and end and start > end:
            reversed_dates.append(f"hạng mục #{item.id} '{item.name}': {start} sau {end}")
    if unpaired:
        report.fail("Khai lẻ ngày", ", ".join(unpaired))
    else:
        report.ok("Cặp ngày kế hoạch", "không có hạng mục nào khai lẻ một ngày")
    if reversed_dates:
        for line in reversed_dates:
            report.fail("Ngày đảo", line)
    else:
        report.ok("Thứ tự ngày", "không có hạng mục nào bắt đầu sau khi kết thúc")


def check_one_entry_per_day(report: Report, project_id: int | None) -> None:
    print("\n7. Mỗi hạng mục chỉ một phiếu mỗi ngày")
    query = db.session.query(
        ProgressEntry.progress_item_id,
        ProgressEntry.report_date,
        db.func.count(ProgressEntry.id).label("total"),
    )
    if project_id is not None:
        query = query.filter(ProgressEntry.project_id == project_id)
    duplicates = (
        query.group_by(ProgressEntry.progress_item_id, ProgressEntry.report_date)
        .having(db.func.count(ProgressEntry.id) > 1)
        .all()
    )
    if duplicates:
        for item_id, report_date, total in duplicates:
            report.fail("Trùng phiếu", f"hạng mục #{item_id} ngày {report_date} có {total} phiếu")
    else:
        report.ok("Một phiếu một ngày", "không có cặp nào bị trùng")


def summarise(project_id: int | None) -> None:
    print("\n8. Quy mô dữ liệu hiện tại")
    scope = lambda query, model: (  # noqa: E731
        query.filter(model.project_id == project_id) if project_id is not None else query
    )
    types = scope(ProgressType.query, ProgressType).count()
    groups = scope(ProgressGroup.query, ProgressGroup).count()
    items = scope(ProgressItem.query, ProgressItem).count()
    entries = scope(ProgressEntry.query, ProgressEntry).count()
    dated = scope(
        ProgressItem.query.filter(ProgressItem.planned_start_date.isnot(None)), ProgressItem
    ).count()
    print(f"  loại tiến độ: {types}")
    print(f"  khu vực:      {groups}")
    print(f"  hạng mục:     {items} (đã khai ngày: {dated}, chưa khai: {items - dated})")
    print(f"  phiếu:        {entries}")
    if items and dated == 0:
        print("  ghi chú: chưa hạng mục nào khai ngày nên biểu đồ Gantt sẽ rỗng.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", type=int, default=None, help="Chỉ kiểm một dự án")
    args = parser.parse_args()

    app = create_app()
    report = Report()
    with app.app_context():
        uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        masked = uri.split("@")[-1] if "@" in uri else uri
        print(f"Kiểm mô đun tiến độ trên database: …@{masked}")
        if args.project_id is not None:
            print(f"Phạm vi: chỉ dự án #{args.project_id}")

        check_schema(report)
        check_migration_head(report)
        check_permissions(report)
        check_accumulation(report, args.project_id)
        check_declared_precision(report, args.project_id)
        check_dates(report, args.project_id)
        check_one_entry_per_day(report, args.project_id)
        summarise(args.project_id)

    print("\n" + "=" * 64)
    if report.failures:
        print(f"KẾT QUẢ: {len(report.failures)} vi phạm cần xử lý")
        for line in report.failures:
            print(f"  - {line}")
        return 1
    print("KẾT QUẢ: mọi bất biến đúng")
    if report.notes:
        for line in report.notes:
            print(f"  ghi chú: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
