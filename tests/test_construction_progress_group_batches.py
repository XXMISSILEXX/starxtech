from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.date_utils import local_today
from app.extensions import db
from app.models import AuditLog, ProgressEntry, ProgressGroup, ProgressItem, ProgressType


def _login(client):
    client.post("/login", data={"username_or_email": "pm", "password": "password123"})


def _structure(*, with_second_item=False, with_entries=False):
    progress_type = ProgressType(project_id=1, name="Tiến độ batch", created_by_id=1)
    db.session.add(progress_type); db.session.flush()
    group = ProgressGroup(project_id=1, progress_type_id=progress_type.id, name="Khu vực gốc", created_by_id=1)
    db.session.add(group); db.session.flush()
    item = ProgressItem(project_id=1, progress_group_id=group.id, name="Hạng mục mịn", unit="m", decimal_places=1, planned_quantity=Decimal("200.0"), created_by_id=1)
    db.session.add(item); db.session.flush()
    second = None
    if with_second_item:
        second = ProgressItem(project_id=1, progress_group_id=group.id, name="Hạng mục hợp lệ", unit="m", decimal_places=0, planned_quantity=Decimal("10"), created_by_id=1)
        db.session.add(second); db.session.flush()
    if with_entries:
        db.session.add_all([
            ProgressEntry(project_id=1, progress_item_id=item.id, report_date=date(2026, 1, 1), quantity=Decimal("151.5"), created_by_id=3),
            ProgressEntry(project_id=1, progress_item_id=item.id, report_date=date(2026, 1, 2), quantity=Decimal("2.0"), created_by_id=3),
        ])
    db.session.commit()
    return progress_type.id, group.id, item.id, None if second is None else second.id


def _item_form_row(index, *, item_id=None, name="Hạng mục ngày", planned_start_date="", planned_end_date="", actual_start_date=""):
    row = {
        f"items-{index}-name": name,
        f"items-{index}-unit": "m",
        f"items-{index}-decimal_places": "0",
        f"items-{index}-planned_quantity": "10",
        f"items-{index}-opening_quantity": "0",
        f"items-{index}-planned_start_date": planned_start_date,
        f"items-{index}-planned_end_date": planned_end_date,
        f"items-{index}-actual_start_date": actual_start_date,
    }
    if item_id is not None:
        row[f"items-{index}-id"] = str(item_id)
    return row


def _assert_date_error_on_row(page, *, index, field, message):
    marker = f'name="items-{index}-{field}"'
    field_html = page[page.index(marker) - 200:page.index(marker) + 500]
    assert "is-invalid" in field_html
    assert message in field_html


@pytest.mark.parametrize("route", ("create", "update"))
@pytest.mark.parametrize(
    ("case", "invalid_dates", "field", "message"),
    (
        (
            "planned_dates_must_be_paired",
            {"planned_start_date": "2026-08-01"},
            "planned_start_date",
            "Cần khai cả ngày bắt đầu và ngày kết thúc kế hoạch, hoặc để trống cả hai.",
        ),
        (
            "planned_dates_must_be_ordered",
            {"planned_start_date": "2026-08-02", "planned_end_date": "2026-08-01"},
            "planned_start_date",
            "Ngày bắt đầu kế hoạch không được sau ngày kết thúc kế hoạch.",
        ),
        (
            "actual_start_cannot_be_future",
            {"actual_start_date": (local_today() + timedelta(days=1)).isoformat()},
            "actual_start_date",
            "Ngày bắt đầu thực tế không được sau hôm nay.",
        ),
        (
            "invalid_date_is_rejected",
            {"planned_start_date": "ngay-khong-hop-le", "planned_end_date": "2026-08-01"},
            "planned_start_date",
            "Ngày bắt đầu kế hoạch phải theo định dạng YYYY-MM-DD.",
        ),
    ),
)
def test_group_batch_date_validation_reopens_overlay_and_rolls_back_every_row(client, app, route, case, invalid_dates, field, message):
    with app.app_context():
        if route == "create":
            progress_type = ProgressType(project_id=1, name=f"Tiến độ tạo ngày {case}", created_by_id=1)
            db.session.add(progress_type)
            db.session.commit()
            target = f"/projects/1/progress/types/{progress_type.id}/groups/batch"
            data = {"name": "Khu vực không được tạo"}
            data.update(_item_form_row(0, name="Hạng mục hợp lệ", planned_start_date="2026-08-01", planned_end_date="2026-08-02"))
            data.update(_item_form_row(1, name="Hạng mục lỗi", **invalid_dates))
            original = None
        else:
            _, group_id, first_item_id, second_item_id = _structure(with_second_item=True)
            target = f"/projects/1/progress/groups/{group_id}/batch"
            data = {"name": "Khu vực không được sửa"}
            data.update(_item_form_row(0, item_id=first_item_id, name="Hạng mục hợp lệ đã sửa", planned_start_date="2026-08-01", planned_end_date="2026-08-02"))
            data.update(_item_form_row(1, item_id=second_item_id, name="Hạng mục lỗi", **invalid_dates))
            original = (group_id, first_item_id, second_item_id)

    _login(client)
    response = client.post(target, data=data)
    page = response.get_data(as_text=True)

    assert response.status_code == 400
    assert message in page
    _assert_date_error_on_row(page, index=1, field=field, message=message)
    assert page.index("data-open-progress-modal") < page.index("construction-progress-overlays.js")
    if route == "create":
        assert 'data-open-progress-modal="createGroup"' in page
        with app.app_context():
            assert ProgressGroup.query.filter_by(progress_type_id=progress_type.id).count() == 0
            assert ProgressItem.query.count() == 0
            assert AuditLog.query.count() == 0
    else:
        assert f'data-open-progress-modal="editGroup-{original[0]}"' in page
        with app.app_context():
            group = db.session.get(ProgressGroup, original[0])
            first_item = db.session.get(ProgressItem, original[1])
            second_item = db.session.get(ProgressItem, original[2])
            assert group.name == "Khu vực gốc"
            assert first_item.name == "Hạng mục mịn"
            assert first_item.planned_start_date is None
            assert second_item.name == "Hạng mục hợp lệ"
            assert second_item.planned_end_date is None
            assert ProgressItem.query.filter_by(progress_group_id=group.id).count() == 2
            assert AuditLog.query.count() == 0


def _allowed_date_cases():
    today = local_today()
    return (
        ("planned_dates_in_past", "2020-01-01", "2020-01-31", "", date(2020, 1, 1), date(2020, 1, 31), None),
        ("planned_dates_in_future", (today + timedelta(days=10)).isoformat(), (today + timedelta(days=20)).isoformat(), "", today + timedelta(days=10), today + timedelta(days=20), None),
        ("actual_start_before_plan", (today - timedelta(days=5)).isoformat(), (today - timedelta(days=3)).isoformat(), (today - timedelta(days=6)).isoformat(), today - timedelta(days=5), today - timedelta(days=3), today - timedelta(days=6)),
        ("actual_start_without_plan", "", "", (today - timedelta(days=2)).isoformat(), None, None, today - timedelta(days=2)),
        ("all_dates_empty", "", "", "", None, None, None),
    )


@pytest.mark.parametrize("route", ("create", "update"))
@pytest.mark.parametrize(
    ("case", "planned_start", "planned_end", "actual_start", "expected_start", "expected_end", "expected_actual"),
    _allowed_date_cases(),
)
def test_group_batch_allows_permitted_date_combinations(client, app, route, case, planned_start, planned_end, actual_start, expected_start, expected_end, expected_actual):
    with app.app_context():
        if route == "create":
            progress_type = ProgressType(project_id=1, name=f"Tiến độ được phép {case}", created_by_id=1)
            db.session.add(progress_type)
            db.session.commit()
            target = f"/projects/1/progress/types/{progress_type.id}/groups/batch"
            data = {"name": "Khu vực ngày được phép"}
            data.update(_item_form_row(0, name="Hạng mục ngày được phép", planned_start_date=planned_start, planned_end_date=planned_end, actual_start_date=actual_start))
            item_id = None
        else:
            _, group_id, item_id, _ = _structure()
            target = f"/projects/1/progress/groups/{group_id}/batch"
            data = {"name": "Khu vực ngày đã sửa"}
            data.update(_item_form_row(0, item_id=item_id, name="Hạng mục ngày đã sửa", planned_start_date=planned_start, planned_end_date=planned_end, actual_start_date=actual_start))

    _login(client)
    response = client.post(target, data=data)

    assert response.status_code == 302
    with app.app_context():
        if route == "create":
            group = ProgressGroup.query.filter_by(progress_type_id=progress_type.id).one()
            item = ProgressItem.query.filter_by(progress_group_id=group.id).one()
        else:
            item = db.session.get(ProgressItem, item_id)
        assert item.planned_start_date == expected_start
        assert item.planned_end_date == expected_end
        assert item.actual_start_date == expected_actual


def test_create_group_batch_rejects_duplicate_names_in_payload_and_keeps_form_values(client, app):
    with app.app_context():
        progress_type = ProgressType(project_id=1, name="Tiến độ mới", created_by_id=1)
        db.session.add(progress_type); db.session.commit()
        type_id = progress_type.id
    _login(client)
    response = client.post(
        f"/projects/1/progress/types/{type_id}/groups/batch",
        data={
            "name": "Khu vực người dùng vừa nhập",
            "items-0-name": "Ống cấp nước", "items-0-unit": "m", "items-0-decimal_places": "1", "items-0-planned_quantity": "10.0", "items-0-opening_quantity": "0",
            "items-1-name": "ống cấp nước", "items-1-unit": "m", "items-1-decimal_places": "1", "items-1-planned_quantity": "12.0", "items-1-opening_quantity": "0",
        },
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "bị trùng trong khu vực" in page
    assert "Khu vực người dùng vừa nhập" in page
    assert "Ống cấp nước" in page
    assert 'data-open-progress-modal="createGroup"' in page
    assert page.index('data-open-progress-modal') < page.index('construction-progress-overlays.js')
    assert 'data-overlay-error-summary>Không thể lưu. Hãy kiểm tra các ô được đánh dấu.</p>' in page
    page_flash = page.split('<main class="main-content">', 1)[1].split('data-open-progress-modal', 1)[0]
    assert "Không thể lưu" not in page_flash
    assert 'name="items-1-name"' in page
    assert "Tên hạng mục &#39;ống cấp nước&#39; bị trùng trong khu vực." in page
    with app.app_context():
        assert ProgressGroup.query.filter_by(progress_type_id=type_id).count() == 0
        assert ProgressItem.query.count() == 0
        assert AuditLog.query.count() == 0


def test_edit_group_batch_rejects_lower_precision_and_rolls_back_every_row(client, app):
    with app.app_context():
        type_id, group_id, precise_item_id, legal_item_id = _structure(with_second_item=True, with_entries=True)
    _login(client)
    response = client.post(
        f"/projects/1/progress/groups/{group_id}/batch",
        data={
            "name": "Khu vực đã sửa nhưng phải rollback",
            "items-0-id": str(precise_item_id), "items-0-name": "Hạng mục mịn", "items-0-unit": "m", "items-0-decimal_places": "0", "items-0-planned_quantity": "200", "items-0-opening_quantity": "0",
            "items-1-id": str(legal_item_id), "items-1-name": "Hạng mục hợp lệ đã sửa", "items-1-unit": "m", "items-1-decimal_places": "0", "items-1-planned_quantity": "99", "items-1-opening_quantity": "0",
            "items-2-name": "Hạng mục lẽ ra được tạo", "items-2-unit": "m", "items-2-decimal_places": "0", "items-2-planned_quantity": "5", "items-2-opening_quantity": "0",
        },
    )
    page = response.get_data(as_text=True)
    assert response.status_code == 400
    assert "Không thể hạ xuống 0 chữ số thập phân" in page
    assert "151,5" in page
    assert "Khu vực đã sửa nhưng phải rollback" in page
    assert "Hạng mục hợp lệ đã sửa" in page
    assert f'data-open-progress-modal="editGroup-{group_id}"' in page
    assert page.index('data-open-progress-modal') < page.index('construction-progress-overlays.js')
    assert 'data-overlay-error-summary>Không thể lưu. Hãy kiểm tra các ô được đánh dấu.</p>' in page
    page_flash = page.split('<main class="main-content">', 1)[1].split('data-open-progress-modal', 1)[0]
    assert "Không thể lưu" not in page_flash
    assert 'name="items-0-decimal_places"' in page
    with app.app_context():
        group = db.session.get(ProgressGroup, group_id)
        precise = db.session.get(ProgressItem, precise_item_id)
        legal = db.session.get(ProgressItem, legal_item_id)
        assert group.name == "Khu vực gốc"
        assert precise.decimal_places == 1
        assert legal.name == "Hạng mục hợp lệ"
        assert legal.planned_quantity == Decimal("10")
        assert ProgressItem.query.filter_by(progress_group_id=group_id).count() == 2
        assert ProgressEntry.query.filter_by(progress_item_id=precise_item_id).count() == 2
        assert ProgressType.query.filter_by(id=type_id).count() == 1
        assert AuditLog.query.count() == 0


def test_edit_group_overlay_shows_real_entry_count_before_item_deletion(client, app):
    with app.app_context():
        type_id, _, _, _ = _structure(with_entries=True)
    _login(client)
    page = client.get(f"/projects/1/progress/types/{type_id}").get_data(as_text=True)
    assert "sẽ xoá 2 phiếu" in page


def test_group_batches_create_and_apply_edit_delete_in_one_save(client, app):
    with app.app_context():
        progress_type = ProgressType(project_id=1, name="Tiến độ thao tác", created_by_id=1)
        db.session.add(progress_type); db.session.commit()
        type_id = progress_type.id
    _login(client)
    created = client.post(
        f"/projects/1/progress/types/{type_id}/groups/batch",
        data={"name": "Khu mới", "items-0-name": "Hạng mục mới", "items-0-unit": "m", "items-0-decimal_places": "1", "items-0-planned_quantity": "12.5", "items-0-opening_quantity": "1.0"},
    )
    assert created.status_code == 302
    with app.app_context():
        group = ProgressGroup.query.filter_by(progress_type_id=type_id, name="Khu mới").one()
        item = ProgressItem.query.filter_by(progress_group_id=group.id).one()
        group_id, item_id = group.id, item.id
        db.session.add(ProgressEntry(project_id=1, progress_item_id=item_id, report_date=date(2026, 1, 1), quantity=Decimal("1.0"), created_by_id=3))
        db.session.commit()
    edited = client.post(
        f"/projects/1/progress/groups/{group_id}/batch",
        data={
            "name": "Khu đã sửa", "confirm_deletions": "on",
            "items-0-id": str(item_id), "items-0-name": "Hạng mục mới", "items-0-unit": "m", "items-0-decimal_places": "1", "items-0-planned_quantity": "12.5", "items-0-opening_quantity": "1.0", "items-0-delete": "on",
            "items-1-name": "Hạng mục thêm", "items-1-unit": "cái", "items-1-decimal_places": "0", "items-1-planned_quantity": "3", "items-1-opening_quantity": "0",
        },
    )
    assert edited.status_code == 302
    with app.app_context():
        db.session.expire_all()
        group = db.session.get(ProgressGroup, group_id)
        assert group.name == "Khu đã sửa"
        assert [item.name for item in group.items] == ["Hạng mục thêm"]
        assert ProgressEntry.query.filter_by(progress_item_id=item_id).count() == 0


def test_create_group_batch_assigns_item_display_order_from_payload_rows(client, app):
    with app.app_context():
        progress_type = ProgressType(project_id=1, name="Tiến độ thứ tự tạo", created_by_id=1)
        db.session.add(progress_type)
        db.session.commit()
        type_id = progress_type.id

    _login(client)
    response = client.post(
        f"/projects/1/progress/types/{type_id}/groups/batch",
        data={
            "name": "Khu vực thứ tự tạo",
            **_item_form_row(0, name="HM01"),
            **_item_form_row(1, name="HM02"),
            **_item_form_row(2, name="HM03"),
        },
    )

    assert response.status_code == 302
    with app.app_context():
        group = ProgressGroup.query.filter_by(progress_type_id=type_id).one()
        assert [(item.name, item.display_order) for item in group.items] == [
            ("HM01", 0),
            ("HM02", 1),
            ("HM03", 2),
        ]


def test_update_group_batch_reassigns_item_display_order_when_payload_rows_are_reordered(client, app):
    with app.app_context():
        _, group_id, first_item_id, second_item_id = _structure(with_second_item=True)

    _login(client)
    response = client.post(
        f"/projects/1/progress/groups/{group_id}/batch",
        data={
            "name": "Khu vực gốc",
            **_item_form_row(0, item_id=second_item_id, name="Hạng mục hợp lệ"),
            **_item_form_row(1, item_id=first_item_id, name="Hạng mục mịn"),
        },
    )

    assert response.status_code == 302
    with app.app_context():
        db.session.expire_all()
        group = db.session.get(ProgressGroup, group_id)
        assert [(item.id, item.display_order) for item in group.items] == [
            (second_item_id, 0),
            (first_item_id, 1),
        ]
