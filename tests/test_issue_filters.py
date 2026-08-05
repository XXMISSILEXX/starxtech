from datetime import date, datetime

import pytest

from app.extensions import db
from app.models import PersistentIssue, PersistentIssueSection, ReportCategory


def login(client, username_or_email, password="password123"):
    return client.post("/login", data={"username_or_email": username_or_email, "password": password})


def _issue(issue_id, title, *, project_id=1, severity="LOW", status="OPEN", opened_date=date(2026, 8, 5), sections=()):
    issue = PersistentIssue(
        id=issue_id,
        project_id=project_id,
        title=title,
        severity=severity,
        status=status,
        opened_date=opened_date,
        closed_date=date(2026, 8, 5) if status == "CLOSED" else None,
        created_by_user_id=1,
    )
    db.session.add(issue)
    db.session.flush()
    for sort_order, section_data in enumerate(sections):
        section = PersistentIssueSection(
            persistent_issue_id=issue.id,
            report_category_id=section_data.get("category_id", 1),
            owner_user_id=section_data.get("owner_user_id"),
            severity=section_data.get("severity", "LOW"),
            status=section_data.get("status", "OPEN"),
            due_date=section_data.get("due_date"),
            sort_order=sort_order,
            created_by_id=1,
        )
        if section_data.get("deleted"):
            section.deleted_at = datetime(2026, 8, 5)
        db.session.add(section)
    return issue


def _list_urls(query=""):
    suffix = f"?{query}" if query else ""
    return (f"/reports/issues{suffix}", f"/reports/projects/1/issues{suffix}")


def test_each_issue_filter_returns_the_expected_rows_on_both_lists(client, app):
    with app.app_context():
        _issue(6101, "High severity", severity="HIGH")
        _issue(6102, "Processing status", status="PROCESSING")
        _issue(6103, "Early opened", opened_date=date(2026, 8, 1))
        _issue(6104, "Safety section", sections=({"category_id": 1},))
        _issue(6105, "Assigned section", sections=({"category_id": 2, "owner_user_id": 3},))
        db.session.commit()
    login(client, "super")

    cases = (
        ("severity=HIGH", b"High severity"),
        ("status=PROCESSING", b"Processing status"),
        ("date_from=2026-08-01&date_to=2026-08-01", b"Early opened"),
        ("category_id=1", b"Safety section"),
        ("owner_user_id=3", b"Assigned section"),
    )
    for query, expected_title in cases:
        for url in _list_urls(query):
            response = client.get(url)
            assert response.status_code == 200
            assert expected_title in response.data


def test_section_filters_use_open_live_sections_and_do_not_duplicate_issues(client, app):
    with app.app_context():
        _issue(6201, "Duplicate match", sections=({"category_id": 1, "owner_user_id": 3}, {"category_id": 2, "owner_user_id": 3}))
        _issue(6202, "Resolved section", sections=({"category_id": 1, "status": "RESOLVED"},))
        _issue(6203, "Closed section", sections=({"category_id": 1, "status": "CLOSED"},))
        _issue(6204, "Deleted section", sections=({"category_id": 1, "deleted": True},))
        _issue(6205, "Owner resolved", sections=({"category_id": 2, "owner_user_id": 3, "status": "RESOLVED"},))
        _issue(6206, "Owner closed", sections=({"category_id": 2, "owner_user_id": 3, "status": "CLOSED"},))
        _issue(6207, "Owner deleted", sections=({"category_id": 2, "owner_user_id": 3, "deleted": True},))
        _issue(6208, "Owner open", sections=({"category_id": 2, "owner_user_id": 3},))
        db.session.commit()
    login(client, "super")

    for url in _list_urls("category_id=1"):
        category_response = client.get(url)
        assert category_response.status_code == 200
        assert category_response.data.count(b"Duplicate match") == 1
        for title in (b"Resolved section", b"Closed section", b"Deleted section"):
            assert title not in category_response.data

    for url in _list_urls("owner_user_id=3"):
        owner_response = client.get(url)
        assert owner_response.data.count(b"Duplicate match") == 1
        assert b"Owner open" in owner_response.data
        for title in (b"Owner resolved", b"Owner closed", b"Owner deleted"):
            assert title not in owner_response.data


def test_combined_filters_intersect_instead_of_expanding_results(client, app):
    with app.app_context():
        _issue(6301, "Only high", severity="HIGH", sections=({"category_id": 1},))
        _issue(6302, "Only safety", severity="LOW", sections=({"category_id": 1},))
        _issue(6303, "Both filters", severity="HIGH", sections=({"category_id": 1},))
        db.session.commit()
    login(client, "super")

    response = client.get("/reports/issues?severity=HIGH&category_id=1")
    assert b"Both filters" in response.data
    assert b"Only safety" not in response.data


def test_closed_issues_are_hidden_by_default_but_resolved_issues_remain_visible(client, app):
    with app.app_context():
        _issue(6401, "Closed issue", status="CLOSED")
        _issue(6402, "Resolved issue", status="RESOLVED")
        db.session.commit()
    login(client, "super")

    response = client.get("/reports/issues")
    assert b"Closed issue" not in response.data
    assert b"Resolved issue" in response.data
    assert "Đang ẩn 1 vấn đề đã đóng.".encode() in response.data

    response = client.get("/reports/issues?show_closed=1")
    assert b"Closed issue" in response.data
    assert b"Resolved issue" in response.data


def test_empty_list_and_nonmatching_filter_have_distinct_messages(client, app):
    login(client, "super")
    empty_response = client.get("/reports/issues")
    assert "Không có vấn đề tồn đọng.".encode() in empty_response.data

    with app.app_context():
        _issue(6451, "Only low", severity="LOW")
        db.session.commit()
    filtered_response = client.get("/reports/issues?severity=HIGH")
    assert "Không có vấn đề nào khớp bộ lọc.".encode() in filtered_response.data
    assert "Không có vấn đề tồn đọng.".encode() not in filtered_response.data


def test_filters_cannot_expand_reporter_project_scope(client, app):
    with app.app_context():
        _issue(6501, "Assigned issue", project_id=1, sections=({"category_id": 1},))
        _issue(6502, "Other project issue", project_id=2, sections=({"category_id": 3},))
        db.session.commit()
    login(client, "reporter")

    response = client.get("/reports/issues?category_id=3")
    assert response.status_code == 200
    assert b"Other project issue" not in response.data
    assert "Loại hạng mục không hợp lệ.".encode() in response.data


@pytest.mark.parametrize("url", ("/reports/issues", "/reports/projects/1/issues"))
def test_issue_lists_paginate_and_preserve_filter_state(client, app, url):
    with app.app_context():
        for number in range(25):
            _issue(
                6600 + number,
                f"Paged {number:02d}",
                severity="HIGH",
                sections=({"category_id": 1, "owner_user_id": 3},),
            )
        db.session.commit()
    login(client, "super")

    separator = "&" if "?" in url else "?"
    filters = "severity=HIGH&status=OPEN&date_from=2026-08-05&date_to=2026-08-05&category_id=1&owner_user_id=3&show_closed=0"
    first_page = client.get(f"{url}{separator}{filters}&page=1")
    second_page = client.get(f"{url}{separator}{filters}&page=2")

    assert first_page.status_code == second_page.status_code == 200
    assert sum(f"Paged {number:02d}".encode() in first_page.data for number in range(25)) == 20
    assert sum(f"Paged {number:02d}".encode() in second_page.data for number in range(25)) == 5
    assert b"severity=HIGH" in first_page.data
    assert b"status=OPEN" in first_page.data
    assert b"date_from=2026-08-05" in first_page.data
    assert b"date_to=2026-08-05" in first_page.data
    assert b"category_id=1" in first_page.data
    assert b"owner_user_id=3" in first_page.data
    assert b"show_closed=0" in first_page.data
    assert b"page=2" in first_page.data


@pytest.mark.parametrize("url", ("/reports/issues", "/reports/projects/1/issues"))
def test_issue_list_page_values_are_clamped_and_out_of_range_is_empty(client, app, url):
    with app.app_context():
        _issue(6701, "Single issue")
        db.session.commit()
    login(client, "super")

    for value in ("0", "-1", "abc"):
        response = client.get(f"{url}?page={value}")
        assert response.status_code == 200
        assert b"Single issue" in response.data
    response = client.get(f"{url}?page=999")
    assert response.status_code == 200
    assert b"Single issue" not in response.data
    assert 'aria-label="Phân trang"'.encode() not in response.data


def test_issue_list_omits_pagination_for_twenty_or_fewer_rows(client, app):
    with app.app_context():
        for number in range(20):
            _issue(6800 + number, f"No pagination {number:02d}")
        db.session.commit()
    login(client, "super")

    response = client.get("/reports/issues")
    assert response.status_code == 200
    assert 'aria-label="Phân trang"'.encode() not in response.data
